from .streaks import StreaksBaseIE
from ..utils import (
    clean_html,
    int_or_none,
    parse_iso8601,
    url_or_none,
)
from ..utils.traversal import traverse_obj


class TBSJPBaseIE(StreaksBaseIE):
    _CU_BASE = 'https://cu.tbs.co.jp'

    def _window_app(self, webpage, name, item_id, fatal=True):
        return self._search_json(
            r'window\.app\s*=', webpage, f'{name} info', item_id, fatal=fatal)


class TBSJPEpisodeIE(TBSJPBaseIE):
    IE_DESC = 'TBS FREE'

    _VALID_URL = r'https?://cu\.tbs\.co\.jp/episode/(?P<id>[\d_]+)'
    _GEO_BYPASS = False
    _TESTS = [{
        'url': 'https://cu.tbs.co.jp/episode/14694_2090934_1000117476',
        'info_dict': {
            'id': '14694_2090934_1000117476',
            'ext': 'mp4',
            'title': '次世代リアクション王発掘トーナメント',
            'cast': 'count:7',
            'categories': 'count:8',
            'description': 'md5:0f57448221519627dce7802432729159',
            'display_id': 'ref:14694_2090934_1000117476',
            'duration': 2761,
            'episode': '次世代リアクション王発掘トーナメント',
            'episode_id': '14694_2090934_1000117476',
            'episode_number': 335,
            'genres': 'count:1',
            'live_status': 'not_live',
            'modified_date': '20250611',
            'modified_timestamp': 1749647146,
            'release_date': '20250611',
            'release_timestamp': 1749646802,
            'series': '水曜日のダウンタウン',
            'series_id': '14694',
            'thumbnail': r're:https?://asset\.catalog\.play\.jp/tbs/tbs_free/.+\.jpg',
            'timestamp': 1749547434,
            'upload_date': '20250610',
            'uploader': 'TBS',
            'uploader_id': 'tbs',
        },
        'skip': 'Geo-restricted to Japan; available for 7 days',
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        meta = self._window_app(webpage, 'episode', video_id, fatal=False)
        episode = traverse_obj(meta, ('falcorCache', 'catalog', 'episode', video_id, 'value'))

        return {
            **self._extract_from_streaks_api(
                'tbs', f'ref:{video_id}', headers={'Referer': f'{self._CU_BASE}/'}),
            **traverse_obj(episode, {
                'title': ('title', ..., 'value', {str}, any),
                'cast': ('credit', ..., 'name', ..., 'value', {str}, any, {lambda x: x.split(',')}, filter),
                'categories': ('keywords', ..., {str}, filter, all, filter),
                'description': ('description', ..., 'value', {clean_html}, any),
                'duration': ('tv_episode_info', 'duration', {int_or_none}),
                'episode': ('title', lambda _, v: not v.get('is_phonetic'), 'value', {str}, any),
                'episode_id': ('content_id', {str}),
                'episode_number': ('tv_episode_info', 'episode_number', {int_or_none}),
                'genres': ('genre', ..., {str}, filter, all, filter),
                'release_timestamp': ('pub_date', {parse_iso8601}),
                'series': ('custom_data', 'program_name', {str}),
                'tags': ('tags', ..., {str}, filter, all, filter),
                'thumbnail': ('artwork', ..., 'url', {url_or_none}, any),
                'timestamp': ('created_at', {parse_iso8601}),
                'uploader': ('tv_show_info', 'networks', ..., {str}, any),
            }),
            **traverse_obj(episode, ('tv_episode_info', {
                'duration': ('duration', {int_or_none}),
                'episode_number': ('episode_number', {int_or_none}),
                'series_id': ('show_content_id', {str}),
            })),
            'id': video_id,
        }


class TBSJPProgramIE(TBSJPBaseIE):
    _VALID_URL = r'https?://cu\.tbs\.co\.jp/program/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://cu.tbs.co.jp/program/14694',
        'info_dict': {
            'id': '14694',
            'title': '水曜日のダウンタウン',
            'description': 'md5:cf1d46c76c2755d7f87512498718b837',
        },
        'playlist_mincount': 1,
    }]

    def _real_extract(self, url):
        program_id = self._match_id(url)
        webpage = self._download_webpage(url, program_id)
        program = self._window_app(
            webpage, 'program', program_id,
        )['falcorCache']['catalog']['program'][program_id]['false']['value']

        entries = [self.url_result(
            f'{self._CU_BASE}/episode/{ep_id}', TBSJPEpisodeIE,
        ) for ep_id in traverse_obj(program, (
            'custom_data', 'seriesList', 'episodeCode', ..., {str}, filter, all, filter))]

        return self.playlist_result(
            entries, program_id, **traverse_obj(program, ('custom_data', {
                'title': ('program_name', {clean_html}),
                'description': ('program_description', {clean_html}),
            })),
        )


class TBSJPPlaylistIE(TBSJPBaseIE):
    _VALID_URL = r'https?://cu\.tbs\.co\.jp/playlist/(?P<id>[\da-f]+)'
    _TESTS = [{
        'url': 'https://cu.tbs.co.jp/playlist/184f9970e7ba48e4915f1b252c55015e',
        'info_dict': {
            'id': '184f9970e7ba48e4915f1b252c55015e',
            'title': 'まもなく配信終了',
        },
        'playlist_mincount': 2,
    }]

    def _entries(self, playlist):
        for entry in traverse_obj(playlist, (
            'catalogs', 'value', lambda _, v: v['content_id'],
        )):
            content_id = entry['content_id']
            content_type = entry.get('content_type')

            if content_type == 'tv_show':
                yield self.url_result(
                    f'{self._CU_BASE}/program/{content_id}', TBSJPProgramIE)
            elif content_type == 'tv_episode':
                yield self.url_result(
                    f'{self._CU_BASE}/episode/{content_id}', TBSJPEpisodeIE)
            else:
                self.report_warning(
                    f'Skipping "{content_id}" with unsupported content_type "{content_type}"')

    def _real_extract(self, url):
        playlist_id = self._match_id(url)
        webpage = self._download_webpage(url, playlist_id)
        playlist = self._window_app(
            webpage, 'playlist', playlist_id)['falcorCache']['playList'][playlist_id]

        return self.playlist_result(
            self._entries(playlist), playlist_id, traverse_obj(playlist, ('display_name', 'value', {str})))
