import datetime as dt
import urllib.parse

from .streaks import StreaksBaseIE
from ..utils import (
    ExtractorError,
    GeoRestrictedError,
    int_or_none,
    make_archive_id,
    parse_qs,
    smuggle_url,
    str_or_none,
    time_seconds,
)
from ..utils.traversal import (
    require,
    traverse_obj,
    trim_str,
)


class TVerBaseIE(StreaksBaseIE):
    _HEADERS = {
        'Origin': 'https://tver.jp',
        'Referer': 'https://tver.jp/',
    }

    def _real_initialize(self):
        session_info = self._download_json(
            'https://platform-api.tver.jp/v2/api/platform_users/browser/create',
            None, 'Creating session', data=b'device_type=pc')
        TVerBaseIE._PLATFORM_QUERY = traverse_obj(session_info, ('result', {
            'platform_uid': 'platform_uid',
            'platform_token': 'platform_token',
        }))
        TVerBaseIE._STREAKS_API_INFO = self._download_json(
            'https://player.tver.jp/player/streaks_info_v2.json', None,
            'Downloading STREAKS API info', 'Unable to download STREAKS API info')

    def _call_api(self, api_type, path, video_id, fatal=False, query=None, **kwargs):
        api_base = {
            'platform': 'https://platform-api.tver.jp/service',
            'service': 'https://service-api.tver.jp',
        }.get(api_type)

        return self._download_json(
            f'{api_base}/api/{path}{f"/{video_id}" if video_id else ""}',
            video_id, fatal=fatal, headers={'x-tver-platform-type': 'web'},
            query={**self._PLATFORM_QUERY, **(query or {})}, **kwargs)

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
            'episode_number': ('no', {int_or_none}),
            'release_timestamp': ('viewStatus', 'startAt', {int_or_none}),
            'season_id': ('seasonID', {str_or_none}),
            'series': ('share', 'text', {trim_str(end='\n#TVer')}),
            'series_id': ('seriesID', {str_or_none}),
            'tags': ('tags', ..., 'name', {str}, filter, all, filter),
        })


class TVerIE(TVerBaseIE):
    IE_NAME = 'tver'
    IE_DESC = 'TVer'
    BRIGHTCOVE_URL_TEMPLATE = 'http://players.brightcove.net/%s/default_default/index.html?videoId=%s'

    _VALID_URL = r'https?://tver\.jp/(?P<type>corner|episodes?|feature|lp)/(?P<id>[a-zA-Z0-9]+)(?:[/#?]|$)'
    _TESTS = [{
        'url': 'https://tver.jp/episodes/epnypkoulf',
        'info_dict': {
            'id': 'epnypkoulf',
            'ext': 'mp4',
            'title': 'クロちゃん、寝て起きたら川のほとりにいてその向こう岸に亡くなった父親がいたら死の淵にいるかと思う説 ほか',
            'alt_title': '7月30日(水)放送分',
            'channel': 'TBS',
            'channel_id': 'tbs',
            'description': 'md5:8f54c919216b8b4b3a25882cd9c0ce8c',
            'display_id': 'f12ad10a1a8a4cac9122441385ca989f',
            'duration': 2752.016,
            'episode': 'クロちゃん、寝て起きたら川のほとりにいてその向こう岸に亡くなった父親がいたら死の淵にいるかと思う説 ほか',
            'episode_id': 'epnypkoulf',
            'episode_number': 341,
            'live_status': 'not_live',
            'modified_date': '20250730',
            'modified_timestamp': 1753871410,
            'release_date': '20250730',
            'release_timestamp': 1753883820,
            'season_id': 's0000501',
            'series': '水曜日のダウンタウン',
            'series_id': 'srf5mcrw4o',
            'tags': 'count:1',
            'thumbnail': r're:https://.+\.jpg',
            'timestamp': 1753838792,
            'upload_date': '20250730',
            'uploader_id': 'tver-tbs',
            '_old_archive_ids': ['brightcovenew f12ad10a1a8a4cac9122441385ca989f'],
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
        media_id = traverse_obj(ep_info, (
            top_key, (id_key, ('videoRefID', {lambda x: f'ref:{x}' if x else None})),
            {str_or_none}, filter, any, {require(f'{id_key} for {backend.capitalize()}')}))

        common_info = {
            'thumbnails': self._thumbnails('episode', video_id),
            **self._parse_tver_metadata(ep_info),
        }
        if backend == 'streaks':
            project_id = ep_info[top_key]['projectID']
            key_idx = dt.datetime.fromtimestamp(time_seconds(hours=9), dt.timezone.utc).month % 6 or 6

            try:
                streaks_info = self._extract_from_streaks_api(project_id, media_id, {
                    **self._HEADERS,
                    'X-Streaks-Api-Key': self._STREAKS_API_INFO[project_id]['api_key'][f'key0{key_idx}'],
                })
            except GeoRestrictedError as e:
                # Catch and re-raise with metadata_available to support --ignore-no-formats-error
                self.raise_geo_restricted(e.orig_msg, countries=self._GEO_COUNTRIES, metadata_available=True)
                streaks_info = {}

            return {
                **streaks_info,
                **common_info,
                '_old_archive_ids': [make_archive_id('BrightcoveNew', media_id)],
            }
        return {
            '_type': 'url_transparent',
            'url': smuggle_url(
                self.BRIGHTCOVE_URL_TEMPLATE % (ep_info[top_key]['accountID'], media_id),
                {'geo_countries': self._GEO_COUNTRIES}),
            'ie_key': 'BrightcoveNew',
            **common_info,
        }


class TVerLiveIE(TVerBaseIE):
    IE_NAME = 'tver:live'
    LIVE_24H = ['FNN フジテレビNEWS24！', 'TBS NEWS DIG Powered by JNN', '日テレNEWS24']

    _VALID_URL = r'https?://tver\.jp/live/(?P<type>simul|special|{})(?:/(?P<id>[\w-]+))?(?:[/#?]|$)'.format(
        '|'.join(('cx', 'ex', 'ntv', 'tbs', 'tx')))
    _TESTS = [{
        'url': 'https://tver.jp/live/simul/lekdgpf369',
        'info_dict': {
            'id': 'lekdgpf369',
            'ext': 'mp4',
            'title': 'ＷＢＳ\u3000巨大地震…経済活動に影響は？▽日産決算…復活は？',
            'alt_title': '7月30日(水)放送分',
            'channel': 'テレ東',
            'channel_id': 'tx',
            'description': 'md5:f33ef76842bbde69e31d5533ed020069',
            'display_id': 'ref:lekdgpf369',
            'duration': 3374.972,
            'episode': 'ＷＢＳ\u3000巨大地震…経済活動に影響は？▽日産決算…復活は？',
            'episode_id': 'lekdgpf369',
            'episode_number': 1,
            'live_status': 'post_live',
            'modified_date': '20250730',
            'modified_timestamp': 1753883801,
            'release_date': '20250730',
            'release_timestamp': 1753880400,
            'season_id': 's0000152',
            'series': 'ＷＢＳ（ワールドビジネスサテライト）',
            'series_id': 'srx2o7o3c8',
            'tags': 'count:5',
            'thumbnail': r're:https://.+\.jpg',
            'timestamp': 1753880400,
            'upload_date': '20250730',
            'uploader_id': 'tver-simul-tx',
        },
    }, {
        'url': 'https://tver.jp/live/tbs',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        video_type, video_id = self._match_valid_url(url).groups()
        now = time_seconds()

        if not video_id:
            timeline = 'v1/call{}LiveTimeline{}'.format(
                *(('', f'/{video_type}'), ('Special', ''))[video_type == 'special'])

            video_id = traverse_obj(self._call_api('service', timeline, None), (
                'result', 'contents', lambda _, v: (
                    (c := v['content'])['onairStartAt'] <= now < c['onairEndAt']
                    and c['title'] not in self.LIVE_24H
                ), 'content', 'id', any))
            if not video_id:
                if video_type == 'special':
                    self.report_warning(
                        '24-hour streams are excluded. For these, please use the individual stream url')
                raise ExtractorError('This channel is offline', True)

        esc = self._call_api(
            'service', 'v1/callEpisodeStatusCheck', None, fatal=True,
            query={'episode_id': video_id, 'type': 'live'}, expected_status=404)
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
            return self.url_result(
                f'https://tver.jp/episodes/{content["id"]}', TVerIE)

        live_info = self._download_json(
            f'https://statics.tver.jp/content/live/{video_id}.json', video_id)
        project_id, media_id = traverse_obj(live_info, (key, ('projectID', 'mediaID')))

        return {
            **self._extract_from_streaks_api(
                project_id, media_id,
                {**self._HEADERS, 'X-Streaks-Api-Key': video_id},
                ssai=content['title'] not in self.LIVE_24H),
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
            video_type = d['type']
            if video_type != 'live':
                path, ie = type_map[video_type]
                yield self.url_result(
                    f'https://tver.jp/{path}/{d["content"]["id"]}', ie)


class TVerPlaylistIE(TVerPlaylistBaseIE):
    IE_NAME = 'tver:playlist'

    _VALID_URL = r'https?://tver\.jp/(?P<type>{})(?:/(?P<id>[\w-]+))?(?:/episodes)?'.format(
        '|'.join(('ender', 'newer', 'series', 'rankings/episode', r'specials/[\w-]+', 'tags', 'talents', 'topics')))
    _TESTS = [{
        'url': 'https://tver.jp/series/srqbg9lpzc',
        'info_dict': {
            'id': 'srqbg9lpzc',
        },
        'playlist_mincount': 14,
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
        'playlist_mincount': 9,
    }, {
        'url': 'https://tver.jp/search/%E3%83%8B%E3%83%A5%E3%83%BC%E3%82%B9?genre=news_documentary&weekday=mon&tvnetwork=jnn',
        'info_dict': {
            'id': 'ニュース',
        },
        'playlist_mincount': 49,
    }]

    def _real_extract(self, url):
        keyword = urllib.parse.unquote(self._match_id(url))
        playlist_info = self._call_api(
            'platform', 'v2/callKeywordSearch', None, query={
                'filterKey': ','.join(v[0].replace(' ', ',') for v in parse_qs(url).values()),
                'keyword': keyword,
            })

        return self.playlist_result(self._entries(playlist_info, (...,)), keyword)
