import urllib.parse

from .streaks import StreaksBaseIE
from ..utils import (
    ExtractorError,
    make_archive_id,
    parse_qs,
    smuggle_url,
    str_or_none,
    time_seconds,
)
from ..utils.traversal import traverse_obj


class TVerBaseIE(StreaksBaseIE):
    def _real_initialize(self):
        session_info = self._download_json(
            'https://platform-api.tver.jp/v2/api/platform_users/browser/create',
            None, 'Creating session', data=b'device_type=pc')
        TVerBaseIE._PLATFORM_QUERY = traverse_obj(session_info, ('result', {
            'platform_uid': 'platform_uid',
            'platform_token': 'platform_token',
        }))

    def _call_api(self, api_type, path, video_id, fatal=False, query=None, **kwargs):
        api_base = {
            'platform': 'https://platform-api.tver.jp/service',
            'service': 'https://service-api.tver.jp',
        }[api_type]

        return self._download_json(
            f'{api_base}/api/{path}{f"/{video_id}" if video_id else ""}',
            video_id, fatal=fatal, headers={
                'x-tver-platform-type': 'web',
            }, query=self._PLATFORM_QUERY | (query or {}), **kwargs,
        )

    @staticmethod
    def _thumbnails(content_type, video_id):
        return [{
            'id': quality,
            'url': f'https://statics.tver.jp/images/content/thumbnail/{content_type}/{quality}/{video_id}.jpg',
            'width': width,
            'height': height,
        } for quality, (width, height) in {
            'small': (480, 270),
            'medium': (640, 360),
            'large': (960, 540),
            'xlarge': (1280, 720),
        }.items()]

    @staticmethod
    def _parse_tver_metadata(json_data):
        return traverse_obj(json_data, {
            'id': ('id', {str_or_none}),
            'title': ('title', {str}),
            'alt_title': ('broadcastDateLabel', {str}),
            'channel': ('broadcastProviderLabel', {str}),
            'channel_id': (('broadcastChannelID', 'broadcastProviderID'), {str_or_none}, any),
            'description': ('description', {str}),
            'episode': ('title', {str}),
            'episode_id': ('id', {str_or_none}),
            'episode_number': ('no', {int}),
            'release_timestamp': ('viewStatus', 'startAt', {int}),
            'season_id': ('seasonID', {str_or_none}),
            'series': ('share', 'text', {lambda x: x.replace('\n#TVer', '')}),
            'series_id': ('seriesID', {str_or_none}),
            'tags': ('tags', ..., 'name', {str}),
        })


class TVerIE(TVerBaseIE):
    IE_NAME = 'tver'
    IE_DESC = 'TVer'
    BRIGHTCOVE_URL_TEMPLATE = 'http://players.brightcove.net/%s/default_default/index.html?videoId=%s'

    _VALID_URL = r'https?://tver\.jp/(?P<type>corner|episodes?|feature|lp)/(?P<id>[a-zA-Z0-9]+)(?:[/#?]|$)'
    _TESTS = [{
        'url': 'https://tver.jp/episodes/epr06ianm0',
        'info_dict': {
            'id': 'epr06ianm0',
            'ext': 'mp4',
            'title': '【TVerアワード2024 バラエティ大賞「水曜日のダウンタウン」】',
            'alt_title': '',
            'channel': 'TBS',
            'channel_id': 'tbs',
            'description': '2024年TVerで一番見られたバラエティ「水曜日のダウンタウン」 受賞コメント',
            'display_id': 'f3fdaeec738048b198da93c55af333c2',
            'duration': 160.027,
            'episode': '【TVerアワード2024 バラエティ大賞「水曜日のダウンタウン」】',
            'episode_id': 'epr06ianm0',
            'episode_number': 321,
            'live_status': 'not_live',
            'release_date': '20250302',
            'release_timestamp': 1740945600,
            'season_id': 'ss7mu95y5p',
            'series': '水曜日のダウンタウン',
            'series_id': 'srf5mcrw4o',
            'tags': list,
            'thumbnail': r're:https://.+\.jpg',
            'thumbnails': list,
            'timestamp': 1741150456,
            'upload_date': '20250305',
            'uploader': 'tver-tbs',
            '_old_archive_ids': ['brightcovenew f3fdaeec738048b198da93c55af333c2'],
        },
    }, {
        'url': 'https://tver.jp/corner/f0100684',
        'only_matching': True,
    }, {
        'url': 'https://tver.jp/lp/f0087789',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        video_type, video_id = self._match_valid_url(url).groups()

        if video_type != 'episodes':
            if video_type == 'lp' and video_id in {'episodes', 'series'}:
                return self.url_result(url.replace('lp/', ''))
            webpage = self._download_webpage(url, video_id)
            redirect_url = self._og_search_url(webpage) or self._search_regex(
                r'<link\s+rel="canonical"\s+href="(https?://tver\.jp/[^"]*)"/>', webpage, 'redirect_url')
            if redirect_url == 'https://tver.jp/':
                raise ExtractorError('This URL is currently unavailable', expected=True)
            return self.url_result(redirect_url)

        backend = self._configuration_arg('backend', ['streaks'])[0]
        if backend not in {'brightcove', 'streaks'}:
            raise ExtractorError(f'Invalid backend: {backend}', expected=True)
        top_key, id_key = {
            'brightcove': ('video', 'videoID'),
            'streaks': ('streaks', 'mediaID'),
        }[backend]

        ep_info = self._download_json(
            f'https://statics.tver.jp/content/episode/{video_id}.json', video_id)
        if not (media_id := traverse_obj(ep_info, (
                top_key, (id_key, ('videoRefID', {lambda x: f'ref:{x}'})), {str_or_none}, filter, any))):
            raise ExtractorError(f'Failed to extract {id_key} for {backend.capitalize()}')

        common_info = {
            'thumbnails': self._thumbnails('episode', video_id),
            **self._parse_tver_metadata(ep_info),
        }
        if backend == 'brightcove':
            return {
                '_type': 'url_transparent',
                'url': smuggle_url(
                    self.BRIGHTCOVE_URL_TEMPLATE % (ep_info[top_key]['accountID'], media_id), {'geo_countries': ['JP']}),
                'ie_keys': 'BrightcoveNew',
                **common_info,
            }
        return {
            **self._parse_streaks_metadata(ep_info[top_key]['projectID'], media_id),
            **common_info,
            '_old_archive_ids': [make_archive_id('BrightcoveNew', media_id)],
        }


class TVerLiveIE(TVerBaseIE):
    IE_NAME = 'tver:live'

    _VALID_URL = r'https?://tver\.jp/live/(?P<type>simul|special|{})(?:/(?P<id>[\w-]+))?(?:[/#?]|$)'.format(
        '|'.join(('cx', 'ex', 'ntv', 'tbs', 'tx')))
    _TESTS = [{
        'url': 'https://tver.jp/live/simul/le9zk5xaks',
        'info_dict': {
            'id': 'le9zk5xaks',
            'ext': 'mp4',
            'title': 'ＷＢＳ\u3000不動産価格\u3000地方や都心にも異変!?',
            'alt_title': '3月18日(火)放送分',
            'channel': 'テレ東',
            'channel_id': 'tx',
            'description': 'md5:7abf0f2eb4a12988c1214c8a5cfa2dbc',
            'duration': 3374.971,
            'episode': 'ＷＢＳ\u3000不動産価格\u3000地方や都心にも異変!?',
            'episode_id': 'le9zk5xaks',
            'live_status': 'post_live',
            'release_date': '20250318',
            'release_timestamp': 1742302800,
            'season_id': 's0000152',
            'series': 'ＷＢＳ（ワールドビジネスサテライト）',
            'series_id': 'srx2o7o3c8',
            'tags': list,
            'thumbnail': r're:https://.+\.jpg',
            'thumbnails': list,
            'timestamp': 1742302800,
            'uploader': 'tver-simul-tx',
            'upload_date': '20250318',
        },
    }, {
        'url': 'https://tver.jp/live/tbs',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        video_type, video_id = self._match_valid_url(url).groups()
        live24h = ['FNN フジテレビNEWS24！', 'TBS NEWS DIG Powered by JNN', '日テレNEWS24']
        now = time_seconds()

        if not video_id:
            timeline = 'v1/call{}LiveTimeline{}'.format(
                *(('', f'/{video_type}'), ('Special', ''))[video_type == 'special'])

            video_id = traverse_obj(self._call_api('service', timeline, None), (
                'result', 'contents', lambda _, v: (
                    (c := v['content'])['onairStartAt'] <= now < c['onairEndAt']
                    and c['title'] not in live24h
                ), 'content', 'id', any))
            if not video_id:
                if video_type == 'special':
                    self.report_warning(
                        '24-hour streams are excluded. For these, please use the individual stream url')
                self.raise_no_formats('This channel is offline', True)

        esc = self._call_api(
            'service', 'v1/callEpisodeStatusCheck', None,
            fatal=True, query={
                'episode_id': video_id,
                'type': 'live',
            }, expected_status=404,
        )
        if esc.get('code') == 70006:
            raise ExtractorError('This live is no longer available', expected=True)

        content = esc['result']['content']
        if esc['result']['type'] == 'live':
            if now < content['startAt']:
                raise ExtractorError('This live has not yet started', expected=True)
            elif content['startAt'] <= now < content['endAt']:
                live_status = 'is_live'
                key = 'liveVideo'
            elif content['isDVRNow']:
                live_status = 'post_live'
                key = 'dvrVideo'
            else:
                raise ExtractorError(
                    'The live has ended, no archive is available', expected=True)
        else:
            return self.url_result(f'https://tver.jp/episodes/{content["id"]}', TVerIE)

        live_info = self._download_json(
            f'https://statics.tver.jp/content/live/{video_id}.json', video_id)
        project_id, media_id = traverse_obj(live_info, (key, ('projectID', 'mediaID')))

        return {
            **self._parse_streaks_metadata(
                project_id, media_id, ssai=content['title'] not in live24h),
            **self._parse_tver_metadata(live_info),
            'live_status': live_status,
            'thumbnails': self._thumbnails('live', video_id),
            'timestamp': content['startAt'],
        }


class TVerPlaylistBaseIE(TVerBaseIE):
    def _entries(self, playlist_info, keys):
        type_map = {
            'episode': ('episodes', TVerIE),
            'series': ('series', TVerPlaylistIE),
        }

        for d in traverse_obj(playlist_info, ('result', 'contents', *keys)):
            if (_type := d['type']) != 'live':
                path, ie = type_map[_type]
                yield self.url_result(
                    f'https://tver.jp/{path}/{d["content"]["id"]}', ie)


class TVerPlaylistIE(TVerPlaylistBaseIE):
    IE_NAME = 'tver:playlist'

    _VALID_URL = r'https?://tver\.jp/(?P<type>{})(?:/(?P<id>[\w-]+))?(?:/episodes)?'.format(
        '|'.join(('ender', 'newer', 'series', 'rankings/episode', r'specials/[\w-]+', 'tags', 'talents', 'topics')))
    _TESTS = [{
        'url': 'https://tver.jp/series/src565pb2j',
        'info_dict': {
            'id': 'src565pb2j',
        },
        'playlist_mincount': 12,
    }, {
        'url': 'https://tver.jp/rankings/episode/drama',
        'info_dict': {
            'id': 'drama',
        },
        'playlist_count': 50,
    }, {
        'url': 'https://tver.jp/ender/anime',
        'info_dict': {
            'id': 'anime',
        },
        'playlist_count': 100,
    }]

    def _real_extract(self, url):
        playlist_type, playlist_id = self._match_valid_url(url).groups()

        api_type, endpoint, keys = {
            'series': ('platform', 'v1/callSeriesEpisodes', (..., 'contents', ...)),
            'specials': ('platform', 'v1/callSpecialContentsDetail', ('content', 'contents')),
            'tags': ('platform', 'v1/callTagSearch', (...,)),
            'talents': ('platform', 'v1/callTalentEpisode', (...,)),
            'ender': ('service', f'v1/callEnderDetail{"/all" * (not playlist_id)}', ('contents', ...)),
            'newer': ('service', f'v1/callNewerDetail{"/all" * (not playlist_id)}', ('contents', ...)),
            'rankings': ('service', 'v1/callEpisodeRankingDetail', ('contents', ...)),
            'topics': ('service', 'v1/callTopics', (..., 'content', 'content')),
        }[playlist_type.split('/')[0]]
        playlist_info = self._call_api(api_type, endpoint, playlist_id)

        return self.playlist_result(
            self._entries(playlist_info, keys), playlist_id or playlist_type)


class TVerSearchIE(TVerPlaylistBaseIE):
    IE_NAME = 'tver:search'

    _VALID_URL = r'https?://(?:www\.)?tver\.jp/search/(?P<id>[^\?]+)(?:\?|$)'
    _TESTS = [{
        'url': 'https://tver.jp/search/%E3%83%A9%E3%83%B4%E3%82%A3%E3%83%83%E3%83%88%EF%BC%81',
        'info_dict': {
            'id': 'ラヴィット！',
        },
        'playlist_mincount': 12,
    }, {
        'url': 'https://tver.jp/search/%E3%83%8B%E3%83%A5%E3%83%BC%E3%82%B9?genre=news_documentary&weekday=mon&tvnetwork=jnn',
        'info_dict': {
            'id': 'ニュース',
        },
        'playlist_mincount': 41,
    }]

    def _real_extract(self, url):
        keyword = urllib.parse.unquote(self._match_id(url))
        playlist_info = self._call_api(
            'platform', 'v2/callKeywordSearch', None, query={
                'filterKey': ','.join(v[0].replace(' ', ',') for v in parse_qs(url).values()),
                'keyword': keyword,
            },
        )

        return self.playlist_result(self._entries(playlist_info, (...,)), keyword)
