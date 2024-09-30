import json
import requests
import os
import sys
from urllib.parse import urljoin
from tqdm import tqdm
from PIL import Image
import io

from concurrent.futures import ThreadPoolExecutor

from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, USLT, TIT2, TPE1, TALB
from mutagen.flac import FLAC, Picture

def special_replace(s):
    v2=[
        ["<", "＜"],
        [">", "＞"],
        ["\\", "＼"],
        ["/", "／"],
        [":", "："],
        ["?", ""],
        ["*", "＊"],
        ["\"", "＂"],
        ["|", "｜"],
        ["*", ""],
        ["...", " "],
        ["?",""]
    ]
    for i in v2:
        s=s.replace(i[0],i[1])
    return s
def merged_lyric(lyric: str, tlyric: str) -> str:
    # 去除末尾的空白字符
    lyric_t = lyric.strip()
    tlyric_t = tlyric.strip()

    # 使用字典存储翻译歌词，键为时间，值为对应的歌词
    tlyric_map = {}

    # 处理翻译歌词，每行按"]"分割，存储到字典
    for line in tlyric_t.splitlines():
        parts = line.split("]", 1)
        if len(parts) == 2:
            time = parts[0][1:]  # 提取时间
            text = parts[1]  # 提取歌词
            tlyric_map[time] = text

    merged = ""

    # 处理主歌词
    for line in lyric_t.splitlines():
        parts = line.split("]", 1)
        if len(parts) == 1: continue
        time = parts[0][1:]  # 提取时间
        text = parts[1]  # 提取歌词

        # 如果翻译歌词没有对应时间戳，直接添加原歌词
        if time not in tlyric_map:
            merged += f"[{time}]{text}\n"
        else:
            # 否则，合并两行歌词
            merged += f"[{time}]{text}\n[{time}]{tlyric_map[time]}\n"

    return merged

def png2jpg(png_bytes: bytes) -> bytes:
    # 将 PNG 字节流转换为图像对象
    with Image.open(io.BytesIO(png_bytes)) as img:
        rgb_img = img.convert('RGB')
        rgb_img.save(io.BytesIO(), format='JPEG')
        jpg_bytes = jpg_bytes_io.getvalue()
    return jpg_bytes


class NeteaseCloudMusicApiClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def get(self, path, **kwargs):
        full_url = urljoin(self.base_url, path)
        return requests.get(full_url, **kwargs)


class MusicDownload:

    def __init__(self, playlist_id):

        self.NeteaseCloudMusicApi = NeteaseCloudMusicApiClient("http://127.0.0.1:3000")

        self.playlist_pic=''
        self.playlist_id=playlist_id
        self.playlist_name=''

        self.require_music={}
        self.all_music={}
        self.already_music={}

        self.music_save_path=''
        with open("./conf.json",'r',encoding='utf-8') as f:
            conf = json.load(f)
            self.playlist_save_path=conf['music_path']
            self.cookie_path=conf['cookie_path']
            self.music_info_path=f"{conf['music_path']}{playlist_id}.json"

    def download(self):
        # Download the music from the given URL
        with open(self.cookie_path,'r') as f:
            cookie=f.read().strip()
        if cookie == '':
            print('请先设置cookie')
            return

        if self.require_music=={}:
            print('没有需要下载的')
            return
        verify=self.NeteaseCloudMusicApi.get("/user/account",cookies={
                "MUSIC_U":cookie,
                'NMTID':'00OdvhJvugK9vXJjk-7v44tYdKKS3wAAAGSPV9tIg',
                '__csrf':'58054809ece2e4a7a1d8a93a71df52ae'
                }).json()

        if verify['profile']==None:
            print('cookie无效')
            print(verify)
            return
        
        print('歌单总计 => ',len(self.all_music))
        print("需要下载 => ", len(self.require_music)) 
        result=self.NeteaseCloudMusicApi.get(
            '/song/url/v1', 
            params={'id':','.join(self.require_music.keys()),'level':'lossless'},
            cookies={
                "MUSIC_U":cookie,
                'NMTID':'00OdvhJvugK9vXJjk-7v44tYdKKS3wAAAGSPV9tIg',
                '__csrf':'58054809ece2e4a7a1d8a93a71df52ae'
                }
        ).json()

        os.path.exists(self.music_save_path) or os.makedirs(self.music_save_path)

        print("已经开始下载")
        for i in result['data']:
            if i['url']=='':
                print(f"{i['id']}没有无损音质")
                continue
            if i['url'][-1]=='.':
                print(f"{i['id']}下载链接异常")
                continue

            _id=str(i['id'])
            self.require_music[_id]['url']=i['url']
            self.require_music[_id]['file_type']=i['url'].split('.')[-1]

            music=self.require_music[_id]
            self.save(music)
            match music['file_type']:
                case 'mp3':
                    self.mp3_mated(music)
                case 'flac':
                    self.flac_mated(music)

    def check(self):
        print('开始检查')
        print("歌单总共 => ",len(self.all_music))
        print('歌单记录下载 => ',len(self.already_music))
        print("歌单实际下载 => ",len(os.listdir(self.music_save_path)))
        # a=b=0
        # all_name=[]

        for k,v in self.already_music.items():
            fname=f"{special_replace(v['name'])}.{v['file_type']}"
            # if fname in all_name:
            #     print(fname,'重复')
            # else:
            #     all_name.append(fname)
            path=os.path.join(self.music_save_path,fname)
            if not os.path.exists(path):
                print(f"{fname} 不存在")
                self.require_music[k]=v
            else:
                if v['file_type']=='mp3':
                    audio=MP3(os.path.join(self.music_save_path,fname))
                    if audio.info.length < 60:
                        print(f"{fname} 文件长度异常")
                        os.remove(path)
                        self.require_music[k]=v
                elif v['file_type']=='flac':
                    audio=FLAC(os.path.join(self.music_save_path,fname))
     

                    if audio.info.length < 60:
                        os.remove(path)
                        print(f"{fname} 文件长度异常")
                        self.require_music[k]=v
                
        
        if(len(self.require_music)==0):
            print('没有需要下载的')
        else:
            print("需要下载 => ", len(self.require_music))
            for i in self.require_music.values():
                print(i['name'])
            self.download()
        
    def repair(self):
        print('开始修补')
        if len(self.already_music)>5:
            with ThreadPoolExecutor(max_workers=10) as t:
                for x in self.already_music.values():
                    t.submit(self.repair_match, x)
        else:
            for i in self.already_music.values():
                self.repair_match(i)

    def repair_match(self,i):
        match i['file_type']:
            case 'mp3': 
                print(i['name'],i['file_type'])
                self.mp3_mated(i)
            case 'flac':
                print(i['name'],i['file_type'])
                self.flac_mated(i)

    def get_lyrics(self, _id):
        result=self.NeteaseCloudMusicApi.get('lyric',params= {'id':_id}).json()
        lyric=result['lrc']['lyric']

        if 'pureMusic' not in result or result["pureMusic"] == False:
            return merged_lyric(lyric=lyric, tlyric=result['tlyric']['lyric'])
        else:
            return lyric

    def mp3_mated(self,music):
        # 打开一个 MP3 文件，读取或创建 ID3 标签
        
        path=os.path.join(self.music_save_path, f"{music['name']}.{music['file_type']}")
        audio = ID3(path)

        # 添加或修改简单的元数据（标题、艺术家等）
        audio["TIT2"] = TIT2(encoding=3, text=music['name']) # Title
        audio["TPE1"] = TPE1(encoding=3, text=music['singer'])  # Artist
        audio["TALB"] = TALB(encoding=3, text=music['album'])   # Album

        # 嵌入专辑封面
        res=requests.get(music['pic_url']).content

        if res[0]==173:
            res=png2jpg(res)
        audio['APIC']=APIC(
                encoding=0,        # 3是utf-8
                mime="image/jpeg",  # 图片的MIME类型
                type=3,            # 3是封面图像
                desc=u"Cover",
                data=res
            )


        # 嵌入歌词
        # lyrics = self.get_lyrics(music['id'])
        # audio['USLT']=USLT(
        #         encoding=3,    # 3是utf-8
        #         lang="eng",    # 歌词的语言
        #         desc="Lyrics",
        #         text=lyrics)
        

        # 保存更改
        audio.save(v2_version=3)

    def flac_mated(self, music):
        # 打开 FLAC 文件
        path=os.path.join(self.music_save_path,f"{music['name']}.{music['file_type']}")
        audio = FLAC(path)

        # 添加/更新元数据
        audio['title'] = music['album']
        audio['artist'] = music['singer']
        audio['album'] = music['album']

        # 如果有专辑封面，嵌入图片
        data=requests.get(music['pic_url']).content
        if data[0]==173:
            data=png2jpg(data)

        picture = Picture()
        picture.data = data

        picture.type = 3  # 3 是封面图片
        picture.mime = "image/jpeg"  # 或者 "image/png" 取决于图片格式
        picture.desc = "Cover"
        audio.clear_pictures()  # 清除已有的图片
        audio.add_picture(picture)  # 添加封面图片

        # 嵌入歌词
        # audio['LYRICS']=self.get_lyrics(music['id'])

        audio.save()

    def save(self,music):
        url=music['url']
        fname=f"{music['name']}.{music['file_type']}"
        # print(music['name'])

        resp = requests.get(url, stream=True)
        # 拿到文件的长度，并把total初始化为0
        total = int(resp.headers.get('content-length', 0))
        path=os.path.join(self.music_save_path,fname)
        print(path)
        # 打开当前目录的fname文件(名字你来传入)
        # 初始化tqdm，传入总数，文件名等数据，接着就是写入，更新等操作了
        with open(path, 'wb') as file, tqdm(
            desc=fname,
            total=total,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in resp.iter_content(chunk_size=1024):
                size = file.write(data)
                bar.update(size)

            self.save_info(music)

    def save_info(self, music):
        self.already_music[music['id']]=music
        data={
                "id": self.playlist_id,
                "name": self.playlist_name,
                "picUrl": self.playlist_pic,
                "total": len(self.already_music),
                'data': list(self.already_music.values())
        }
        with open(self.music_info_path,'w',encoding='utf-8') as f:
            json.dump(data, f)

    def get_song_list(self):
        result=self.NeteaseCloudMusicApi.get('/playlist/detail',params={'id':self.playlist_id})
        result_json=result.json()
        self.playlist_name=result_json['playlist']['name']
        self.music_save_path=os.path.join(self.playlist_save_path,self.playlist_name)
        self.playlist_pic=result_json['playlist']['coverImgUrl']

        for i in range((result_json["playlist"]["trackCount"] + 49) // 50):
            songs=self.NeteaseCloudMusicApi.get('/playlist/track/all',params={'id':self.playlist_id,'limit':50,'offset':50*i}).json()
            for song in songs['songs']:
                # print(song)
                ar=song['ar']
                # ar 长度小于3，直接使用，大于3，取前3个
                if len(ar)<3:
                    singer=','.join([a['name'] for a in ar])
                else:
                    singer=','.join([a['name'] for a in ar[:3]])

                singer=special_replace(singer)
                self.all_music[str(song['id'])]={
                    'id':str(song['id']),
                    'name':f'{singer} - {special_replace(song["name"])}',
                    'pic_url':f"{song['al']['picUrl']}?param=1400y1400",
                    'singer':special_replace(singer),
                    'album':song['al']['name'],
                    'url':'',
                    'file_type':''
                }


        os.path.exists(self.playlist_save_path) or os.makedirs(self.playlist_save_path)
        os.path.exists(self.music_info_path) or open(self.music_info_path,'w').close()
        with open(self.music_info_path,'r',encoding='utf-8') as f:
            if (content:=f.read()) != "":
                data=json.loads(content)
                sub_json=data['data']

                if data['name'] != self.playlist_name:
                    src=os.path.join(self.playlist_save_path, data['name'])
                    os.rename(src, self.playlist_name)

                for i in sub_json:
                    self.already_music[i['id']]=i

        # 差集 计算需要下载的music
        self.require_music = {k: v for k, v in self.all_music.items() if k not in self.already_music.keys()}
    
    def show_playlist(self):
        os.listdir(self.playlist_save_path)
        for i in os.listdir(self.playlist_save_path):
            if i.endswith("json"):
                with open(os.path.join(self.playlist_save_path,i),'r',encoding='utf-8') as f:
                    data=json.load(f)
                    result=self.NeteaseCloudMusicApi.get('/playlist/detail',params={'id':data['id']}).json()
                    print(data['name'],data['id'],data['total'],'/',result["playlist"]["trackCount"])


if __name__ == '__main__':
    if len(sys.argv)==2:
        pid=sys.argv[2]
        m=MusicDownload(pid)
        m.get_song_list()
        match sys.argv[1]:
            case 'check':
                m.check()
            case 'download':
                m.download()
            case 'repair':
                m.repair()
    else:
        m=MusicDownload('')
        m.show_playlist()