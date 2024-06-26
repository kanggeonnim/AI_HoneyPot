from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import os
from app.config.config import settings

# YouTube Data API의 API key를 입력합니다.

youtube_api_key = settings.YOUTUBE_API_KEY


def get_youtube_list_lastest():
    channel_id = 'UCL-WOj1FxKR8Hlzg5tvnWKg'
    # YouTube Data API 클라이언트를 빌드합니다.
    youtube = build('youtube', 'v3', developerKey=youtube_api_key)

    beforeVideos = []

    try:
        # 동영상 목록을 가져옵니다.
        request = youtube.search().list(
            part='id,snippet',
            channelId=channel_id,
            order='date',
            type='video',
            maxResults=3
        )
        response = request.execute();
        videos = list()
        # 동영상 제목과 ID를 출력합니다.
        for item in response['items']:
            video_title = item['snippet']['title']
            published_at = item['snippet']['publishTime'][0:10]
            today = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
            live_broadcast = item['snippet']['liveBroadcastContent']
            tumblr_url = item['snippet']['thumbnails']['high']
            video_id = item['id']['videoId']

            # if (today == published_at and live_broadcast == "none"):
            # if (today != published_at and live_broadcast == "none"):
            videos.append(video_id)
            # print(live_broadcast)
            print(f'{video_title}\n{video_id}\n{tumblr_url}')
            # print(published_at)
            # print("==============================")
            print(videos)

        if len(videos) == 0:
            raise Exception("No videos found")
        return videos
        # beforeVideos.append(video_title)
        # print(beforeVideos)
    except HttpError as e:
        print(f'An HTTP error {e.resp.status} occurred:\n{e.content}')


def get_youtube_list_playlist():
    # 가져올 채널의 ID를 입력합니다.
    playlist_id = 'PLA_P66SgTXS0NKjRM6XcUtFBQVLZLlIXz'
    #   국회방송NATV

    # YouTube Data API 클라이언트를 빌드합니다.
    youtube = build('youtube', 'v3', developerKey=youtube_api_key)

    beforeVideos = []

    try:
        # nextPageToken 이어서 받기
        nextPageToken = 'EAAajgFQVDpDTWdCSWhCQk4wUTBOVGszUVRZM05FRkRPVEUxS0FGSThmcWQwS3lqaFFOUUFWcEVJa05wU2xGVVJVWm1WVVJaTWxVeVpGVlhSazEzVkd0MGNWVnJNREpYUjA1V1pFVmFRMVZXV2sxWGEzaHpVMVpvTmtWbmMwbG9PRTkyYzBGWlVUWlFZbVJMUVNJ'
        request = youtube.playlistItems().list(
            part='snippet',
            playlistId=playlist_id,
            maxResults=50,
            pageToken=nextPageToken
        )
        response = request.execute()
        nextPageToken = response['nextPageToken']

        # 한번에 전체리스트 가져오기
        # while ('nextPageToken' in response):
        #     nextPage = youtube.playlistItems().list(
        #         part='snippet',
        #         playlistId=playlist_id,
        #         maxResults=50,
        #         pageToken=nextPageToken
        #     ).excute()
        #     response['items'] = response['items'] + nextPage['items']
        #
        #     if 'nextPageToken' not in nextPage:
        #         response.pop('nextPageToken', None)
        #     else:
        #         nextPageToken = nextPage['nextPageToken']

        # save scripts
        f = open('../log/token.txt', "a", encoding="utf-8")
        f.write(str(datetime.today()) + '\n')
        f.write(str(nextPageToken) + '\n')
        f.write('------------------------\n')
        f.close()

        videos = list()
        # 동영상 제목과 ID를 출력합니다.
        for item in response['items']:
            video_title = item['snippet']['title']
            # published_at = item['snippet']['publishTime'][0:10]
            published_at = item['snippet']['publishedAt'][0:10]
            today = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
            print(f'today is {today} and published at {published_at}')
            print(f'{video_title}')

            # live_broadcast = item['snippet']['liveBroadcastContent']
            tumblr_url = item['snippet']['thumbnails']['high']
            # video_id = item['id']['videoId']
            video_id = item['snippet']['resourceId']['videoId']

            # if today == published_at and live_broadcast == "none":

            videos.append(video_id)
            # print(live_broadcast)
            # print(f'{video_title}\n{video_id}\n{tumblr_url}')
            # print(published_at)
            # print("==============================")
        print(videos)

        if len(videos) == 0:
            raise Exception("No videos found")

        return videos
        # beforeVideos.append(video_title)

        # print(beforeVideos)

    except HttpError as e:
        print(f'An HTTP error {e.resp.status} occurred:\n{e.content}')


if __name__ == '__main__':
    get_youtube_list_lastest()
    # get_youtube_list_playlist()
