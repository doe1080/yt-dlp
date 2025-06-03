from .common import InfoExtractor
from ..utils import (
    int_or_none,
    parse_qs,
    str_or_none,
    try_call,
    update_url_query,
    url_or_none,
)
from ..utils.traversal import traverse_obj, trim_str


class AnimeFestaBaseIE(InfoExtractor):
    _BASE_URL = 'https://animefesta.iowl.jp/'

    def _real_initialize(self):
        auth = try_call(lambda: self._get_cookies(self._BASE_URL)['festa_auth'].value)
        if not auth:
            self.raise_login_required()

        AnimeFestaBaseIE._HEADERS = {
            'Authorization': auth,
            'X-Requested-With': 'XMLHttpRequest',
        }

    def _call_api(self, path, some_id, query=None):
        return self._download_json(
            f'https://api-animefesta.iowl.jp/v1/{path}/{some_id}',
            some_id, headers=self._HEADERS, query=query,
        ).get('contents', {})


class AnimeFestaIE(AnimeFestaBaseIE):
    IE_NAME = 'animefesta'
    IE_DESC = 'アニメフェスタ'

    _VALID_URL = r'https?://animefesta\.iowl\.jp/(?!titles/)[^?]*\?(?=[^#]*\bplay_episode_id=\d+)(?=[^#]*\btid=\d+)[^#]+'
    _TESTS = [{
        'url': 'https://animefesta.iowl.jp/?play_episode_id=6942&tid=1302',
        'info_dict': {
            'id': '6942',
            'ext': 'mp4',
            'title': '先輩と有言十支族の王',
            'alt_title': '9番湯',
            'cast': 'count:6',
            'description': 'md5:858dd552ef1f4fd8012363fc2e479877',
            'duration': 235,
            'episode': '先輩と有言十支族の王',
            'episode_id': '6942',
            'episode_number': 9,
            'genres': 'count:10',
            'release_year': 2024,
            'series': '名湯『異世界の湯』開拓記 ～アラフォー温泉マニアの転生先は、のんびり温泉天国でした～',
            'series_id': '1302',
            'thumbnail': r're:https?://animefesta-assets\.cdnext\.stream\.ne\.jp/thumbnails/episodes/.+\.jpg',
        },
    }, {
        'url': 'https://animefesta.iowl.jp/premium?play_episode_id=4440&tid=742',
        'info_dict': {
            'id': '4440',
            'ext': 'mp4',
            'title': '一緒に泊まっていいんですか？',
            'age_limit': 18,
            'alt_title': '第1話',
            'cast': 'count:5',
            'description': 'md5:28b0ff1040fadd545df8d4254387c965',
            'duration': 389,
            'episode': '一緒に泊まっていいんですか？',
            'episode_id': '4440',
            'episode_number': 1,
            'genres': 'count:19',
            'release_year': 2022,
            'series': 'ハーレムきゃんぷっ！【プレミアム版】',
            'series_id': '742',
            'thumbnail': r're:https?://animefesta-assets\.cdnext\.stream\.ne\.jp/thumbnails/episodes/.+\.jpg',
        },
    }]

    def _real_extract(self, url):
        query = {k: v[0] for k, v in parse_qs(url).items() if v}
        episode_id, title_id = map(query.get, ('play_episode_id', 'tid'))
        contents = self._call_api('titles', title_id)

        formats = []
        for q in traverse_obj(contents, (
            'exist_image_qualities', {dict.items}, lambda _, v: v[1], 0,
        )):
            m3u8_url = self._call_api(
                'episodes', episode_id, query={'image_quality': q})['playing_url']
            if not m3u8_url:
                continue

            fmts = self._extract_m3u8_formats(m3u8_url, episode_id, 'mp4')
            for fmt in fmts:
                fmt['format_id'] = q
            formats.extend(fmts)
        if not formats:
            self.raise_no_formats('No video found', expected=True)

        return {
            'id': episode_id,
            'episode_id': episode_id,
            'formats': formats,
            'series_id': title_id,
            **traverse_obj(contents, {
                'age_limit': ('is_age_restriction_r18', {bool}, {lambda x: 18 if x else None}),
                'cast': ('tags', 'cast', ..., 'name', {str}),
                'creators': ('production_company', ..., 'name', {str}),
                'genres': ('genres', ..., 'name', {str}),
                'release_year': ('tags', 'produced_year', ..., 'name', {trim_str(end='年')}, {int_or_none}, any),
                'series': ('name', {str}),
            }),
            **traverse_obj(contents, ('episodes', lambda _, v: str(v.get('id')) == episode_id, any, {
                'title': ('name', {str}),
                'alt_title': ('prefix_name', {str}),
                'description': ('summary', {str}),
                'duration': ('sec_length', {int_or_none}),
                'episode': ('name', {str}),
                'episode_id': ('id', {str_or_none}),
                'episode_number': (('episode_number', 'number'), {int_or_none}, any),
                'thumbnail': ('thumbnail_url', {url_or_none}),
            })),
        }


class AnimeFestaTitleIE(AnimeFestaBaseIE):
    IE_NAME = 'animefesta:title'

    _VALID_URL = r'https?://animefesta\.iowl\.jp/(?:titles/|[^?]*\?(?![^#]*\bplay_episode_id=)[^#]*\btid=)(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://animefesta.iowl.jp/titles/1499',
        'info_dict': {
            'id': '1499',
            'title': 'プリンセスラバー！視界良好版',
        },
        'playlist_count': 12,
    }, {
        'url': 'https://animefesta.iowl.jp/?tid=1352',
        'info_dict': {
            'id': '1352',
            'title': 'ヨスガノソラ\u3000パッケージ版',
        },
        'playlist_count': 12,
    }, {
        'url': 'https://animefesta.iowl.jp/search?tid=1092',
        'info_dict': {
            'id': '1092',
            'title': '回復術士のやり直し(やり直し ver.）',
        },
        'playlist_count': 12,
    }]

    def _real_extract(self, url):
        title_id = self._match_id(url)
        contents = self._call_api('titles', title_id)

        entries = [self.url_result(
            update_url_query(self._BASE_URL, {
                'play_episode_id': episode_id,
                'tid': title_id,
            }), AnimeFestaIE,
        ) for episode_id in traverse_obj(contents, ('episodes', ..., 'id', {str_or_none}))]

        return self.playlist_result(entries, title_id, contents.get('name'))
