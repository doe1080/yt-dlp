import re

from .common import InfoExtractor
from .youtube import YoutubeIE
from ..utils import (
    clean_html,
    int_or_none,
    str_or_none,
    unified_timestamp,
    url_or_none,
)
from ..utils.traversal import require, traverse_obj


class BS11PlusIE(InfoExtractor):
    _JSTREAM_BASE = 'https://eqi533pzgh.eq.webcdn.stream.ne.jp/www50/eqe003odff/jmc_pub'
    _VALID_URL = r'https://vod\.bs11\.jp/contents/(?P<id>[\w-]+)'
    _TESTS = [{
        'url': 'https://vod.bs11.jp/contents/w-kyounoehon-20230327',
        'info_dict': {
            'id': 'w-kyounoehon-20230327',
            'ext': 'mp4',
            'title': '「はじめてのおともだち」（国土社 刊）',
            'description': 'md5:18740d0d57a7f93550bbfeb3a0511efe',
            'duration': 230,
            'episode': '「はじめてのおともだち」（国土社 刊）',
            'episode_number': 21,
            'series': '今日のえほん',
            'series_id': '23',
            'thumbnail': r're:https?://.+',
            'timestamp': 1679922000,
            'upload_date': '20230327',
        },
    }, {
        'url': 'https://vod.bs11.jp/contents/w-lycoris_recoil_art_piano-1',
        'info_dict': {
            'id': 'FncrQOKa-ZE',
            'ext': 'mp4',
            'title': '【リコリス・リコイル】黒板アート×ピアノ(さユり「花の塔」) /  Lycoris Recoil × Chalk art × Piano',
            'age_limit': 0,
            'availability': 'public',
            'categories': ['Film & Animation'],
            'channel': '全国無料テレビ BS11',
            'channel_follower_count': int,
            'channel_id': 'UC793WyAnqu2VU5m9mplwfpQ',
            'channel_url': 'https://www.youtube.com/channel/UC793WyAnqu2VU5m9mplwfpQ',
            'comment_count': int,
            'description': 'md5:4446f29e2bc8a51b7dcdac8de2bb4c9d',
            'duration': 290,
            'heatmap': 'count:100',
            'like_count': int,
            'live_status': 'not_live',
            'media_type': 'video',
            'playable_in_embed': True,
            'release_date': '20230421',
            'release_timestamp': 1682071209,
            'tags': 'count:28',
            'thumbnail': r're:https?://i\.ytimg\.com/.+',
            'timestamp': 1682071209,
            'upload_date': '20230421',
            'uploader': '全国無料テレビ BS11',
            'uploader_id': '@BS11index',
            'uploader_url': 'https://www.youtube.com/@BS11index',
            'view_count': int,

        },
        'add_ie': ['Youtube'],
    }]

    def _parse_jsonp(self, callback, string, video_id):
        return self._search_json(rf'{re.escape(callback)}\s*\(', string, callback, video_id)

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        nextjs_data = self._search_nextjs_v13_data(webpage, video_id)
        data = traverse_obj(nextjs_data, (lambda _, v: str_or_none(v['uuid']), 'data', any, {dict}))
        if youtube_id := data.get('youtube_id'):
            return self.url_result(youtube_id, YoutubeIE)

        mid = traverse_obj(data, ('external_id', {str_or_none}, {require('media ID')}))
        eq_meta = self._download_webpage(
            f'{self._JSTREAM_BASE}/eq_meta/v1/{mid}.jsonp', video_id)
        movie = self._parse_jsonp('metaDataResult', eq_meta, video_id)['movie']

        service = self._download_webpage(
            f'{self._JSTREAM_BASE}/jmc_swf/setting/service.jsonp', video_id)
        service_result = self._parse_jsonp('serviceResult', service, video_id)
        cid = traverse_obj(service_result, ('service', 'cid', {str_or_none}))

        access_control = self._download_webpage(
            'https://api01-platform.stream.co.jp/apiservice/getAccessControl',
            video_id, query={'cid': cid, 'domain': url, 'mid': mid})
        crypt_tk = self._parse_jsonp('accessControlResultEq', access_control, video_id)['crypt_tk']

        formats, subtitles = [], {}
        for manifest in traverse_obj(movie, (
            'movie_list_hls', lambda _, v: 'auto' in v['text'],
        )):
            fmts, subs = self._extract_m3u8_formats_and_subtitles(
                f'{self._JSTREAM_BASE}/{manifest["url"]}',
                video_id, 'mp4', query={'__token': crypt_tk})
            self._merge_subtitles(subs, target=subtitles)
            formats.extend(fmts)
        self._remove_duplicate_formats(formats)

        return {
            'id': video_id,
            'formats': formats,
            'subtitles': subtitles,
            **traverse_obj(data, {
                'title': ('title', {clean_html}),
                'description': ('explanation', {clean_html}, filter),
                'episode': ('alternative_text', {clean_html}, filter),
                'episode_number': ('episode_count', {int_or_none}),
                'series': ('program_title', {clean_html}, filter),
                'series_id': ('program_id', {str_or_none}),
                'timestamp': ('stream_start_at', {unified_timestamp(tz_offset=9)}),
            }),
            **traverse_obj(movie, {
                'duration': ('duration', {int_or_none}),
                'thumbnail': ('thumbnail_url', {url_or_none}),
            }),
        }
