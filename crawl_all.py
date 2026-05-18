#!/usr/bin/env python3
"""Recursively crawls all folders in course 696969, saves video manifest."""
import json, sys, time, requests

TOKEN = open('/tmp/classplus_manifest.json').read()
TOKEN = json.loads(TOKEN)['token']

HEADERS = {
    'x-access-token': TOKEN,
    'region': 'IN',
    'Origin': 'https://web.classplusapp.com',
    'Referer': 'https://web.classplusapp.com/',
}

BASE = 'https://api.classplusapp.com'
COURSE_ID = 696969

all_videos = []

def crawl(folder_id, path=''):
    params = {'courseId': str(COURSE_ID), 'folderId': str(folder_id)}
    resp = requests.get(f'{BASE}/v2/course/content/get', params=params, headers=HEADERS, timeout=30)
    data = resp.json()
    if data.get('status') != 'success':
        print(f"  ERROR folder {folder_id}: {data.get('message','?')}")
        return

    items = data['data'].get('courseContent', [])
    subfolders = []
    for item in items:
        ct = item.get('contentType')
        if ct == 1:
            subfolders.append(item)
        elif ct == 2:
            all_videos.append({
                'folder_path': path,
                'name': item.get('name', ''),
                'contentHashId': item.get('contentHashId', ''),
                'duration': item.get('duration', ''),
                'id': item.get('id'),
            })

    if len(all_videos) % 50 == 0 or (not path):
        print(f"[{len(all_videos)} videos] {path or '/'}  {len(subfolders)}F {sum(1 for i in items if i.get('contentType')==2)}V")

    for sf in subfolders:
        new_path = f"{path}/{sf['name']}" if path else sf['name']
        crawl(sf['id'], new_path)
        time.sleep(0.15)

if __name__ == '__main__':
    print("Crawling course 696969 — all folders, all videos...")
    crawl(0)

    out = {
        'course_id': COURSE_ID,
        'total_videos': len(all_videos),
        'videos': all_videos,
    }
    with open('/tmp/classplus_video_manifest.json', 'w') as f:
        json.dump(out, f, indent=2, default=str, ensure_ascii=False)

    print(f"\nDONE. Total videos: {len(all_videos)}")
    print(f"Saved: /tmp/classplus_video_manifest.json")

    # Per-folder summary
    from collections import Counter
    top = Counter(v['folder_path'].split('/')[0] for v in all_videos)
    for name, count in sorted(top.items()):
        print(f"  {name}: {count}")
