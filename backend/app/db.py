from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import get_settings


def make_engine(url: str):
    result = create_engine(url, pool_pre_ping=True, **(
        {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_size":8,"max_overflow":8,"pool_timeout":3}
    ))
    @event.listens_for(result,'before_cursor_execute')
    def before(conn,cursor,statement,parameters,context,executemany):
        import time
        from app.diagnostics import active,checkpoint
        checkpoint();b=active.get()
        if b and conn.dialect.name=='postgresql':
            remaining=max(1,min(5000,int((b.deadline-time.monotonic())*1000)))
            cursor.execute(f'SET LOCAL statement_timeout = {remaining}')
        context.macro_started=time.perf_counter()
    @event.listens_for(result,'after_cursor_execute')
    def after(conn,cursor,statement,parameters,context,executemany):
        import time
        from app.diagnostics import active
        b=active.get()
        if b:b.database_ms+=(time.perf_counter()-context.macro_started)*1000
    @event.listens_for(result,'handle_error')
    def failed(context):
        import time
        from app.diagnostics import active
        b=active.get();execution=context.execution_context
        if b and execution and hasattr(execution,'macro_started'):
            b.database_ms+=(time.perf_counter()-execution.macro_started)*1000
    return result


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session
