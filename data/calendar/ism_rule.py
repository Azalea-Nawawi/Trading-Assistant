from datetime import date, timedelta
def nth_weekday(y,m,wd,n):
    d=date(y,m,1); c=0
    while True:
        if d.weekday()==wd:
            c+=1
            if c==n: return d
        d+=timedelta(1)
def last_weekday(y,m,wd):
    d=date(y,m+1,1)-timedelta(1) if m<12 else date(y,12,31)
    while d.weekday()!=wd: d-=timedelta(1)
    return d
def observed(d):
    return d-timedelta(1) if d.weekday()==5 else d+timedelta(1) if d.weekday()==6 else d
def easter(y):
    a=y%19;b=y//100;c=y%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3;h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32+2*e+2*i-h-k)%7;m=(a+11*h+22*l)//451;mo=(h+l-7*m+114)//31;da=((h+l-7*m+114)%31)+1
    return date(y,mo,da)
def holidays(y, extra):
    h={observed(date(y,1,1)),nth_weekday(y,1,0,3),nth_weekday(y,2,0,3),last_weekday(y,5,0),observed(date(y,6,19)),observed(date(y,7,4)),nth_weekday(y,9,0,1),nth_weekday(y,11,3,4),observed(date(y,12,25)),easter(y)-timedelta(2),date(y,1,2)}
    if extra: h|={nth_weekday(y,10,0,2),observed(date(y,11,11))}
    return h
def bdays(y,m,extra):
    hol=holidays(y,extra); d=date(y,m,1); out=[]
    while d.month==m:
        if d.weekday()<5 and d not in hol: out.append(d)
        d+=timedelta(1)
    return out
def ism(y,m,extra=False):
    b=bdays(y,m,extra); return b[0],b[2]
official2026={1:("2026-01-05","2026-01-07"),2:("2026-02-02","2026-02-04"),3:("2026-03-02","2026-03-04"),4:("2026-04-01","2026-04-06"),5:("2026-05-01","2026-05-05"),6:("2026-06-01","2026-06-03"),7:("2026-07-01","2026-07-06"),8:("2026-08-03","2026-08-05"),9:("2026-09-01","2026-09-03"),10:("2026-10-01","2026-10-05"),11:("2026-11-02","2026-11-04"),12:("2026-12-01","2026-12-03")}
if __name__=="__main__":
    for extra in (False,True):
        bad=[(m,ism(2026,m,extra),official2026[m]) for m in range(1,13) if tuple(str(x) for x in ism(2026,m,extra))!=official2026[m]]
        print("extra holidays" if extra else "base", "mismatch:", bad)
