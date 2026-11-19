"""Pairwise complete statistics; no significance or causal/predictive claims."""
from math import sqrt
from statistics import mean

def ranks(values):
    result=[0.0]*len(values)
    ordered=sorted(range(len(values)),key=lambda i:values[i]);i=0
    while i<len(ordered):
        j=i+1
        while j<len(ordered) and values[ordered[j]]==values[ordered[i]]:j+=1
        for n in ordered[i:j]:result[n]=(i+j-1)/2+1
        i=j
    return result

def correlation(x,y,dates,method='pearson',minimum=12):
    pairs=[(a,b,d) for a,b,d in zip(x,y,dates) if a is not None and b is not None]
    n=len(pairs);value=None
    if n>=minimum:
        a,b,_=map(list,zip(*pairs))
        if method=='spearman':a,b=ranks(a),ranks(b)
        ma,mb=mean(a),mean(b);aa=sum((v-ma)**2 for v in a);bb=sum((v-mb)**2 for v in b)
        if aa>0 and bb>0:value=max(-1,min(1,sum((u-ma)*(v-mb) for u,v in zip(a,b))/sqrt(aa*bb)))
    return dict(value=value,status='AVAILABLE' if value is not None else 'INSUFFICIENT_DATA',sample_count=n,sample_start=pairs[0][2] if pairs else None,sample_end=pairs[-1][2] if pairs else None,missing_ratio=1-n/len(dates) if dates else 1,method=method)

def rolling_statistics(values,dates,window):
    out=[]
    for i,d in enumerate(dates):
        sample=values[max(0,i-window+1):i+1];valid=[v for v in sample if v is not None];complete=len(sample)==window and len(valid)==window
        avg=mean(valid) if complete else None;sd=sqrt(sum((v-avg)**2 for v in valid)/window) if complete else None
        out.append(dict(date=d,mean=avg,std=sd,z_score=(values[i]-avg)/sd if sd else None,percentile=100*sum(v<=values[i] for v in valid)/window if complete else None,sample_count=len(valid),missing_ratio=1-len(valid)/window))
    return out

def sahm(values):
    averages=[mean(values[i-2:i+1]) if i>=2 and all(v is not None for v in values[i-2:i+1]) else None for i in range(len(values))]
    return [a-min(averages[i-12:i]) if i>=14 and a is not None and all(v is not None for v in averages[i-12:i]) else None for i,a in enumerate(averages)]
