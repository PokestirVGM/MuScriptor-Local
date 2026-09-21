"""Held-out rhythm arrangements: measure failures too, never assert perfect Auto.

Actual cached beat model inference on authored audio. Pulse and written meter
are scored separately; matching a subdivision is not a correct meter result.
"""
from pathlib import Path
import json
import sys
import numpy as np
import soundfile as sf
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'upstream'))
from muscriptor.utils.rhythm import detect, Timeline
OUT=ROOT/'build/vgm-final-validation/grooves'
RATE=16000


def case(name,meter,groups,bpm=120,swing=False,syncopated=False,change=False):
    n,d=map(int,meter.split('/'));bar=n*4/d;end=bar*16
    qknots=np.array([0,end/2,end]);bpms=np.array([bpm,bpm*1.25 if change else bpm])
    tknots=np.r_[.5,.5+np.cumsum(np.diff(qknots)*60/bpms)]
    at=lambda q: float(np.interp(q,qknots,tknots))
    samples=np.zeros(round((tknots[-1]+.5)*RATE));rng=np.random.default_rng(151)
    pulse=np.array([b+g for b in np.arange(0,end,bar) for g in groups])
    def add(q,kind,level):
        start=round(at(q)*RATE);t=np.arange(round(.10*RATE))/RATE
        if kind=='kick': wave=np.sin(2*np.pi*(70*t-90*t*t))*np.exp(-45*t)
        elif kind=='hat': wave=rng.normal(size=len(t))*np.exp(-100*t)
        else: wave=(np.sin(2*np.pi*330*t)+.3*np.sin(2*np.pi*660*t))*np.exp(-30*t)
        samples[start:start+len(t)]+=level*wave
    for i,q in enumerate(pulse):
        add(q,'kick',.6 if q%bar==0 else .4)
    for q in np.arange(0,end,1):
        for offset in (0,2/3 if swing else .5):
            if q+offset<end: add(q+offset,'hat',.07)
        melodic=q+(.5 if syncopated else 0)
        if melodic<end: add(melodic,'tone',.22)
    samples/=max(1,float(abs(samples).max()))
    folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
    sf.write(folder/'reference.wav',samples,RATE,subtype='PCM_16')
    detection=detect(torch.tensor(samples[None,:],dtype=torch.float32),RATE)
    (folder/'detection.json').write_text(json.dumps(vars(detection)))
    timeline=Timeline({},detection,len(samples)/RATE)
    grid=timeline.display_grid() if timeline.usable else None
    truth=np.array([at(q) for q in pulse])
    actual=np.array(grid['beats']) if grid else np.array([])
    actual=actual[(actual>=truth[0]-.05)&(actual<=truth[-1]+.05)]
    errors=np.min(abs(truth[:,None]-actual[None,:]),axis=1) if len(actual) else np.array([999.])
    reverse=np.min(abs(actual[:,None]-truth[None,:]),axis=1) if len(actual) else np.array([999.])
    expected=bpms/(groups[1]-groups[0]) if len(groups)>1 and len(set(np.round(np.diff(np.r_[groups,bar]),6)))==1 else None
    record=dict(case=name,reference_meter=meter,reference_pulse_bpms=expected.tolist() if expected is not None else 'unequal beat groups',
        auto_bpm=timeline.bpm,auto_meter=grid['meter'] if grid else None,
        grid_error_ms_p95=float(np.percentile(errors,95)*1000),extra_pulse_error_ms_p95=float(np.percentile(reverse,95)*1000),
        pulse_pass=bool(np.percentile(errors,95)<=.05 and np.percentile(reverse,95)<=.05),
        literal_meter_match=bool(grid and grid['meter']==meter),warnings=timeline.warnings)
    print(json.dumps(record),flush=True);return record


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    report=[case(*args,**kwargs) for args,kwargs in [
        (('swing-4-4','4/4',[0,1,2,3]),{'swing':True}),
        (('syncopation-4-4','4/4',[0,1,2,3]),{'syncopated':True}),
        (('compound-6-8','6/8',[0,1.5]),{}),
        (('compound-9-8','9/8',[0,1.5,3]),{}),
        (('compound-12-8','12/8',[0,1.5,3,4.5]),{}),
        (('grouped-7-8','7/8',[0,1,2]),{}),
        (('syncopated-tempo-step','4/4',[0,1,2,3]),{'syncopated':True,'change':True}),
        (('compound-tempo-step','6/8',[0,1.5]),{'change':True}),
    ]]
    (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
