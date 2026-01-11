from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    float_or_none,
    str_or_none,
    strip_or_none,
    unified_timestamp,
    url_or_none,
)
from ..utils.traversal import traverse_obj


class HibikiBaseIE(InfoExtractor):
    def _call_api(self, path, access_id, query=None):
        return self._download_json(
            f'https://vcms-api.hibiki-radio.jp/api/v1/{path}', access_id,
            headers={'X-Requested-With': 'XMLHttpRequest'}, query=query)

    def _parse_episode(self, access_id, ep_info):
        episode_parts = traverse_obj(ep_info, (
            'episode', 'episode_parts', ..., 'description', {strip_or_none}, filter))

        base_info = {
            'description': '\n\n'.join(s.replace('\r\n', '\n') for s in episode_parts),
            **traverse_obj(ep_info, {
                'cast': ('casts', ..., 'name', {clean_html}, filter),
                'series': ('name', {clean_html}, filter),
                'series_id': ('access_id', {str_or_none}),
                'tags': ('hash_tag', {clean_html}, {lambda x: x.split()}, ..., {str.strip}, filter),
                'thumbnail': ('sp_image_url', {url_or_none}),
                'timestamp': ('episode_updated_at', {unified_timestamp(tz_offset=9)}),
            }),
            **traverse_obj(ep_info, ('episode', {
                'id': ('video', 'id', {str_or_none}),
                'title': ('name', {clean_html}),
                'duration': ('video', 'duration', {float_or_none}),
                'episode': ('name', {clean_html}, filter),
                'episode_id': ('id', {str_or_none}),
            })),
        }

        items = [base_info]
        if traverse_obj(ep_info, ('additional_video_flg', {bool})):
            items.append({
                **base_info,
                **traverse_obj(ep_info, ('episode', 'additional_video', {
                    'id': ('id', {str_or_none}),
                    'duration': ('duration', {float}),
                })),
                'title': f"{base_info['title']}の楽屋裏",
            })

        for item_info in items:
            m3u8_url = self._call_api(
                'videos/play_check', access_id,
                query={'video_id': item_info['id']})['playlist_url']

            yield {
                'formats': self._extract_m3u8_formats(m3u8_url, access_id),
                **item_info,
            }


class HibikiIE(HibikiBaseIE):
    IE_NAME = 'hibiki'
    IE_DESC = '響 - HiBiKi Radio Station -'

    _VALID_URL = r'https?://hibiki-radio\.jp/description/(?P<id>[\w-]+)(/detail)?'
    _TESTS = [{
        'url': 'https://hibiki-radio.jp/description/takeachance/detail',
        'info_dict': {
            'id': '21039',
            'ext': 'm4a',
            'title': '第7回',
            'cast': 'count:3',
            'description': 'md5:de6aef914389b325cd92f9b61c3d552a',
            'duration': 2879.28,
            'episode': '第7回',
            'episode_id': '17157',
            'series': '竹内順子のTake a chance ラジオ ダッシュ！',
            'series_id': 'takeachance',
            'tags': ['#響ラジオ'],
            'thumbnail': r're:https?://image\.hibiki-radio\.jp/.+',
            'timestamp': 1767754800,
            'upload_date': '20260107',
        },
        'skip': 'Expires in two weeks',
    }, {
        'url': 'https://hibiki-radio.jp/description/tsunradi/detail',
        'info_dict': {
            'id': 'tsunradi',
            'title': '新田恵海のえみゅーじっく♪ふらっぐ☆',
        },
        'playlist_count': 2,
    }]

    def _real_extract(self, url):
        access_id = self._match_id(url)
        ep_info = self._call_api(f'programs/{access_id}', access_id)
        if not traverse_obj(ep_info, ('episode', 'video')):
            raise ExtractorError('No episodes found', expected=True)

        return self.playlist_result(
            self._parse_episode(access_id, ep_info), access_id, ep_info['name'])
