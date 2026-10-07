"""유튜브 검색 결과를 조회수순으로 받아 (조회수 | 길이 | 채널 | 제목)을 출력 — 제목·썸네일 문구를 정하기 전에 같은 주제·장르에서 무엇이 실제로 터졌는지 본다.
사용: python -I yt_search.py "토정 이지함" "조선왕조실록 미스터리"
"""
import sys, re, json, subprocess, urllib.parse
def search(q):
    url="https://www.youtube.com/results?search_query="+urllib.parse.quote(q)+"&sp=CAM%253D"  # 조회수순
    r=subprocess.run(['curl','-sS','-m','30','-A','Mozilla/5.0 (Windows NT 10.0; Win64; x64)','-H','Accept-Language: ko-KR,ko;q=0.9',url],capture_output=True)
    s=r.stdout.decode('utf-8','ignore')
    m=re.search(r'var ytInitialData = (\{.*?\});</script>',s)
    if not m: return []
    data=json.loads(m.group(1)); out=[]
    def walk(o):
        if isinstance(o,dict):
            if 'videoRenderer' in o:
                v=o['videoRenderer']
                t=''.join(x.get('text','') for x in v.get('title',{}).get('runs',[]))
                views=v.get('viewCountText',{}).get('simpleText','')
                ch=''.join(x.get('text','') for x in v.get('ownerText',{}).get('runs',[]))
                ln=v.get('lengthText',{}).get('simpleText','')
                out.append((views,ln,ch,t))
            for x in o.values(): walk(x)
        elif isinstance(o,list):
            for x in o: walk(x)
    walk(data); return out
for q in sys.argv[1:]:
    res=search(q); print(f'\n### {q}  ({len(res)})')
    for v in res[:14]: print(' | '.join(v))
