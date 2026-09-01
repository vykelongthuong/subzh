from __future__ import annotations
import concurrent.futures as cf
import html
import json
import os
import random
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

INPUT = Path('input/5.srt')
INPUT_PARTS = Path('input_parts')
OUTPUT = Path('output/sub_5(20260901-212054).srt')
CACHE = Path('output/cache.json')
TM_FILE = Path('tm.json.gz.b64')
MAX_WORKERS = int(os.getenv('MAX_WORKERS','8'))

SRT_RE = re.compile(
    r'(?ms)^\s*(\d+)\s*\n'
    r'(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n'
    r'(.*?)(?=\n\s*\n\s*\d+\s*\n\d{2}:|\Z)'
)
HAN_RE = re.compile(r'[\u3400-\u9fff]')

SOURCE_FIXES = [
    ('水业岛','水叶岛'),('水椰岛','水叶岛'),('水夜岛','水叶岛'),('水液岛','水叶岛'),
    ('水月岛','水叶岛'),('水耶岛','水叶岛'),('水叶头','水叶岛'),
    ('司徒员','司徒远'),('司徒老官','司徒老怪'),('许昌兽','徐长寿'),
    ('楚诗书','楚师叔'),('冷诗书','冷师叔'),('火源诗书','火猿师叔'),
    ('零食','灵石'),('住机','筑基'),('助击','筑基'),('祝鸡','筑基'),('诸暨','筑基'),
    ('修饰','修士'),('元英','元婴'),('非洲','飞舟'),('绿先宗','绿仙宗'),
    ('收复','收服'),('镇法','阵法'),('正牌','阵牌'),('幻镇','幻阵'),
    ('捷丹','结丹'),('劫单','结丹'),('接单','结丹'),('劫丹','结丹'),
    ('猎天鹰','裂天鹰'),('火焰师叔','火猿师叔'),('火焰师术','火猿师叔'),
    ('临时矿','灵石矿'),('性感','气感'),('御府','玉符'),('御符','玉符'),
]

TERM_MAP = {
    '三十六地煞迷雾阵':'Tam Thập Lục Địa Sát Mê Vụ Trận',
    '三十六地煞迷雾镇':'Tam Thập Lục Địa Sát Mê Vụ Trận',
    '水叶岛':'Thủy Diệp Đảo','徐长寿':'Từ Trường Thọ','叶星河':'Diệp Tinh Hà',
    '叶珊瑚':'Diệp San Hô','张宗昌':'Trương Tông Xương','司徒远':'Tư Đồ Viễn',
    '陈太冲':'Trần Thái Xung','黄天狼':'Hoàng Thiên Lang','李林浩':'Lý Lâm Hạo',
    '冷灵儿':'Lãnh Linh Nhi','冷梅':'Lãnh Mai','江小川':'Giang Tiểu Xuyên',
    '楚师叔':'Sở sư thúc','冷师叔':'Lãnh sư thúc','黄师叔':'Hoàng sư thúc',
    '火猿师叔':'Hỏa Viên sư thúc','火猿':'Hỏa Viên','红衣':'Hồng Y','小黑':'Tiểu Hắc',
    '小金':'Tiểu Kim','裂天鹰':'Liệt Thiên Ưng','绿仙宗':'Lục Tiên Tông',
    '万仙阁':'Vạn Tiên Các','万仙楼':'Vạn Tiên Lâu','万宝阁':'Vạn Bảo Các','墨家':'Mặc gia',
    '藏仙渊':'Tàng Tiên Uyên','妖仙长廊':'Yêu Tiên Hành Lang','妖仙走廊':'Yêu Tiên Hành Lang',
    '万鬼大阵':'Vạn Quỷ Đại Trận','养魂玉':'Dưỡng Hồn Ngọc','安魂丹':'An Hồn Đan',
    '空天战船':'Không Thiên Chiến Thuyền','水之灵':'Thủy Chi Linh','血脉玉符':'Huyết Mạch Ngọc Phù',
    '木雷符':'Mộc Lôi Phù','雷暴符':'Lôi Bạo Phù','火球符':'Hỏa Cầu Phù','飞行符':'Phi Hành Phù',
    '风行符':'Phong Hành Phù','水缚符':'Thủy Phược Phù','问心符':'Vấn Tâm Phù','火雷符':'Hỏa Lôi Phù',
    '风雷剑':'Phong Lôi Kiếm','混元棍':'Hỗn Nguyên Côn','储物袋':'túi trữ vật',
    '灵石矿':'mỏ linh thạch','灵石':'linh thạch','筑基丹':'Trúc Cơ Đan','聚气丹':'Tụ Khí Đan',
    '聚灵丹':'Tụ Linh Đan','筑基':'Trúc Cơ','练气':'Luyện Khí','结丹':'Kết Đan','金丹':'Kim Đan',
    '元婴':'Nguyên Anh','化神':'Hóa Thần','炼气':'Luyện Khí','法器':'pháp khí','灵器':'linh khí',
    '伪法器':'ngụy pháp khí','阵法':'trận pháp','阵旗':'trận kỳ','阵牌':'trận bàn',
    '迷雾阵':'Mê Vụ Trận','幻阵':'huyễn trận','符箓':'phù lục','灵符':'linh phù','丹药':'đan dược',
    '飞剑':'phi kiếm','飞舟':'phi chu','妖丹':'yêu đan','妖兽':'yêu thú','妖修':'yêu tu',
    '灵根':'linh căn','神识':'thần thức','灵脉':'linh mạch','洞府':'động phủ','宗门':'tông môn',
    '仙门':'tiên môn','修仙界':'Tu Tiên giới','修仙者':'người tu tiên','修士':'tu sĩ',
    '师尊':'sư tôn','师叔':'sư thúc','师伯':'sư bá','师兄':'sư huynh','师弟':'sư đệ',
    '师姐':'sư tỷ','师妹':'sư muội','弟子':'đệ tử','道友':'đạo hữu','贫道':'bần đạo',
    '老朽':'lão hủ','本座':'bản tọa','老祖':'lão tổ',
}
TERMS = sorted(TERM_MAP.items(), key=lambda kv: len(kv[0]), reverse=True)

POST_REPL = [
    (r'\bbạn\b','ngươi'),(r'\bBạn\b','Ngươi'),(r'\btôi\b','ta'),(r'\bTôi\b','Ta'),
    (r'\banh ấy\b','hắn'),(r'\bAnh ấy\b','Hắn'),(r'\bcô ấy\b','nàng'),(r'\bCô ấy\b','Nàng'),
    (r'đá linh hồn','linh thạch'),(r'đá tâm linh','linh thạch'),
    (r'giai đoạn xây dựng nền móng','cảnh giới Trúc Cơ'),(r'giai đoạn xây nền','cảnh giới Trúc Cơ'),
    (r'Golden Core','Kim Đan'),(r'Nascent Soul','Nguyên Anh'),
]

def parse_srt(path: Path):
    text=path.read_text(encoding='utf-8-sig',errors='replace').replace('\r\n','\n').replace('\r','\n')
    rec=[]
    for m in SRT_RE.finditer(text):
        rec.append({'idx':int(m.group(1)),'time':m.group(2).strip(),'src':' '.join(m.group(3).split())})
    return rec

def fix_source(s: str) -> str:
    s=unicodedata.normalize('NFKC',s)
    for a,b in SOURCE_FIXES: s=s.replace(a,b)
    s=re.sub(r'(?<=\d)万一块', '万块', s)
    return s.strip()

def protect_terms(s: str):
    restored={}
    for term,vi in TERMS:
        if term in s:
            token=f'ZXQ{len(restored):03d}QXZ'
            s=s.replace(term,token); restored[token]=vi
    return s,restored

def restore_terms(s: str, restored: dict[str,str]) -> str:
    for token,vi in restored.items():
        s=re.sub('\\s*'.join(map(re.escape,token)),vi,s,flags=re.I)
    return s

def google_translate(text: str) -> str:
    params=urllib.parse.urlencode({'client':'gtx','sl':'zh-CN','tl':'vi','dt':'t','q':text})
    req=urllib.request.Request('https://translate.googleapis.com/translate_a/single?'+params,headers={
        'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
        'Accept':'application/json,text/plain,*/*'})
    with urllib.request.urlopen(req,timeout=30) as r: data=json.loads(r.read().decode('utf-8'))
    parts=[]
    if isinstance(data,list) and data and isinstance(data[0],list):
        for item in data[0]:
            if item and isinstance(item,list) and item[0]: parts.append(item[0])
    out=''.join(parts).strip()
    if not out: raise RuntimeError('empty translation')
    return out

def clean_vi(s: str) -> str:
    s=unicodedata.normalize('NFC',html.unescape(s)).replace('\n',' ').replace('\r',' ')
    for p,r in POST_REPL: s=re.sub(p,r,s,flags=re.I if p.lower()==p else 0)
    s=re.sub(r'\s+',' ',s).strip(); s=re.sub(r'\s+([,.!?;:])',r'\1',s)
    s=re.sub(r'([,;:])(?=\S)',r'\1 ',s); s=re.sub(r'([.!?])(?=[A-Za-zÀ-ỹĐđ])',r'\1 ',s)
    s=s.replace(' ,',',').replace(' .','.').replace(' ?', '?').replace(' !','!')
    if s and s[0].isalpha(): s=s[0].upper()+s[1:]
    return s.strip(' "')

def translate_one(src: str, tm: dict[str,str], cache: dict[str,str]) -> tuple[str,str]:
    if src in cache: return src,cache[src]
    if src in tm: return src,clean_vi(tm[src])
    fixed=fix_source(src)
    if fixed in tm: return src,clean_vi(tm[fixed])
    if not HAN_RE.search(fixed): return src,clean_vi(fixed)
    protected,restored=protect_terms(fixed); last=None
    for attempt in range(8):
        try:
            out=clean_vi(restore_terms(google_translate(protected),restored))
            if 'ZXQ' in out or not out: raise RuntimeError('bad token or empty translation')
            return src,out
        except Exception as e:
            last=e; time.sleep(min(25,(1.7**attempt)+random.random()*1.5))
    try: return src,clean_vi(google_translate(fixed))
    except Exception: raise RuntimeError(f'cannot translate: {src!r}: {last}')

def main():
    if not INPUT.exists():
        import base64, gzip
        chunks=[p.read_text(encoding='ascii').strip() for p in sorted(INPUT_PARTS.glob('part_*.txt'))]
        if not chunks: raise SystemExit('No input file or encoded input parts')
        INPUT.parent.mkdir(parents=True,exist_ok=True)
        INPUT.write_bytes(gzip.decompress(base64.b64decode(''.join(chunks))))
    records=parse_srt(INPUT)
    if not records: raise SystemExit('No SRT cues parsed')
    if [r['idx'] for r in records] != list(range(1,len(records)+1)): raise SystemExit('Cue numbering is not continuous')
    if TM_FILE.exists():
        import base64,gzip
        tm=json.loads(gzip.decompress(base64.b64decode(TM_FILE.read_text(encoding='ascii'))).decode('utf-8'))
    else: tm={}
    cache={}
    if CACHE.exists():
        try: cache=json.loads(CACHE.read_text(encoding='utf-8'))
        except Exception: cache={}
    unique=[]; seen=set()
    for r in records:
        if r['src'] not in seen: unique.append(r['src']); seen.add(r['src'])
    print(f'cues={len(records)} unique={len(unique)} tm_hits={sum(x in tm for x in unique)} cache={len(cache)}',flush=True)
    todo=[x for x in unique if x not in cache]; done=0; lock=threading.Lock()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs={ex.submit(translate_one,s,tm,cache):s for s in todo}
        for fut in cf.as_completed(futs):
            src,tgt=fut.result()
            with lock:
                cache[src]=tgt; done+=1
                if done%100==0:
                    CACHE.write_text(json.dumps(cache,ensure_ascii=False),encoding='utf-8')
                    print(f'translated {done}/{len(todo)}',flush=True)
    CACHE.write_text(json.dumps(cache,ensure_ascii=False),encoding='utf-8')
    blocks=[]; chinese_left=[]
    for r in records:
        tgt=clean_vi(cache.get(r['src']) or tm.get(r['src']) or '')
        if not tgt: raise SystemExit(f'Missing cue {r["idx"]}')
        if HAN_RE.search(tgt): chinese_left.append((r['idx'],tgt))
        blocks.append(f"{r['idx']}\n{r['time']}\n{tgt}")
    OUTPUT.write_text('\n\n'.join(blocks)+'\n',encoding='utf-8')
    check=parse_srt(OUTPUT)
    if len(check)!=len(records): raise SystemExit(f'Output cue mismatch: {len(check)} vs {len(records)}')
    for a,b in zip(records,check):
        if a['idx']!=b['idx'] or a['time']!=b['time']: raise SystemExit(f'Structure mismatch at cue {a["idx"]}')
    if chinese_left:
        Path('output/chinese_left.json').write_text(json.dumps(chinese_left,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'warning: Chinese remains in {len(chinese_left)} cues',flush=True)
    print(f'WROTE {OUTPUT} cues={len(records)} bytes={OUTPUT.stat().st_size}',flush=True)

if __name__=='__main__': main()
