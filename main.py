import asyncio
import json
import threading
import time

import pyncm_async.apis
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

app = FastAPI()


def netease_login(email, password):
    import os
    if os.path.exists('session.txt'):
        with open('session.txt', 'r') as f:
            session_str = f.read()
            if session_str:
                print('读取session_str成功,使用此session')
            else:
                quit()
            pyncm_async.SetCurrentSession(pyncm_async.LoadSessionFromString(session_str))
            return 1

    else:
        print('不存在session文件，尝试登陆')
        pyncm_async.apis.login.LoginViaEmail(email, password)
        print('登陆成功')
        session_str = pyncm_async.DumpSessionAsString(pyncm_async.GetCurrentSession())
        with open('session.txt', 'w') as f:
            f.write(session_str)
        return 0


def update_login(email, password):
    print('更新线程启动')
    # 每半小时自动更新
    update_time = 60 * 30
    while True:
        time.sleep(update_time)
        # 测试可用性
        result = search_songs(2006721186)
        if result['data'][0]['url'] == None:
            print('session失效,更新中')
            pyncm_async.apis.login.LoginViaEmail(email=email, password=password)
            print('更新成功')
            session_str = pyncm_async.DumpSessionAsString(pyncm_async.GetCurrentSession())
            with open('session.txt', 'w') as f:
                f.write(session_str)
                # 写入新session
            with open('log.txt', 'w') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + '   ' + '更新session成功')


async def search_songs(input_content: str):
    single = True
    for i in range(1):

        # 判断是否纯数字id
        try:
            id = int(input_content)
            break
        except ValueError:
            pass

        # 判断是否链接  使用正则表达式匹配id
        import re
        match = re.search(r'id=(\d+)', input_content)
        if match:
            id = int(str(match.group(1)))
            break

        single = False

        # 其余情况都当做歌名，应当搜索多首歌

    if single:

        # 搜单首
        track_audio, track_detail = await asyncio.gather(pyncm_async.apis.track.GetTrackAudio(id),
                                                         pyncm_async.apis.track.GetTrackDetail(id))
        url = track_audio['data'][0]['url']
        author = track_detail['songs'][0]['ar'][0]['name']
        title = track_detail['songs'][0]['name']
        imageurl = track_detail['songs'][0]['al']['picUrl']
        return [{'url': url, 'author': author, 'title': title, 'imageurl': imageurl}]
    else:
        search_result = await pyncm_async.apis.cloudsearch.GetSearchResult(keyword=input_content)
        # pyncm默认单次获取量30 要处理返回列表不到30个的情况!!
        # 疑似 url和歌名不匹配 原因 返回的list不一定按顺序，需要手动通过id匹配['data'][0]['id'] 目前方案 通过双层循环匹配 待优化
        l = []
        id_list = []
        songs_length = len(search_result['result']['songs'])
        print(json.dumps(search_result, ensure_ascii=False))
        for i in range(songs_length):
            l.append({'title': search_result['result']['songs'][i]['name'],
                      'author': search_result['result']['songs'][i]['ar'][0]['name'],
                      'id': search_result['result']['songs'][i]['id'],
                      'imageurl': search_result['result']['songs'][i]['al']['picUrl']})
            # 同时添加id到idlist准备请求url
            id_list.append(search_result['result']['songs'][i]['id'])
        track_result = await pyncm_async.apis.track.GetTrackAudio(id_list)
        print(json.dumps(track_result, ensure_ascii=False))
        for i in range(songs_length):
            for j in range(songs_length):
                if id_list[i] == track_result['data'][j]['id']:
                    l[i]['url'] = track_result['data'][j]['url']
                    break
        return l


netease_login('test', 'test')
update_thread = threading.Thread(target=update_login, args=('test', 'test'))
update_thread.start()

# src文件夹挂载
app.mount("/src", StaticFiles(directory="src"), name='src_files')


@app.get("/", response_class=HTMLResponse)
async def i():
    with open('index.html', 'r', encoding='utf-8') as f:
        html = f.read()
        return html.encode()


@app.post('/search')
async def search(input: dict):
    # 处理输入为空的情况
    if not (input['input']):
        return 0

    song_details = await search_songs(input['input'])

    return Response(content=json.dumps(song_details, ensure_ascii=False), media_type='application/json')


if __name__ == '__main__':
    uvicorn.run(app, port=80, host='0.0.0.0')
