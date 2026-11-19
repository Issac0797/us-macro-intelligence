"""Public official HTML only; bounded retries and a polite serial request interval."""
import time
from urllib.parse import urlparse
import httpx
from app.providers import ProviderError
class FedProvider:
 def __init__(self,client=None,sleep=time.sleep):
  self.client=client or httpx.Client(timeout=35,follow_redirects=True,headers={'User-Agent':'USMacroIntelligence/0.6 (public economic research)'})
  self.sleep=sleep;self.last=0.;self.attempts=0
 def fetch(self,url):
  if urlparse(url).netloc!='www.federalreserve.gov' or not url.startswith('https://'):raise ProviderError('Official Federal Reserve URL required')
  for attempt in range(4):
   self.sleep(max(0,.6-(time.monotonic()-self.last)));self.last=time.monotonic();self.attempts=attempt+1
   try:
    r=self.client.get(url)
    if r.status_code==200:
     if 'html' not in r.headers.get('content-type',''):raise ProviderError('HTML source required; PDF review needed')
     return r.content.decode('utf-8-sig')
    if r.status_code not in [429,500,502,503,504]:raise ProviderError(f'Official source HTTP {r.status_code}')
    try:delay=min(60,max(0,float(r.headers.get('Retry-After','2'))))
    except ValueError:delay=2**attempt
   except (httpx.TransportError,UnicodeDecodeError):delay=2**attempt
   self.sleep(delay)
  raise ProviderError('Official source retry limit reached')
 def close(self):self.client.close()
