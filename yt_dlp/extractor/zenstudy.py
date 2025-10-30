from .niconico import NiconicoBaseIE
from ..utils import (
    clean_html,
    int_or_none,
    str_or_none,
    update_url,
    url_or_none,
)
from ..utils.traversal import traverse_obj


class ZenStudyBaseIE(NiconicoBaseIE):
    def _call_api(self, version, path, item_id, fatal=False):
        common = 'v1/lessons/' if version == 'v1' else 'v2/material/courses/'
        return self._download_json(
            f'https://api.nnn.ed.nico/{common}/{path}', item_id, fatal=fatal)


class ZenStudyIE(ZenStudyBaseIE):
    IE_NAME = 'zenstudy'

    _VALID_URL = r'https?://(?:www\.)?nnn\.ed\.nico(?:/courses/(?P<course_id>\d+)/chapters/(?P<chapter_id>\d+))?/(?P<type>lessons|movie)/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://www.nnn.ed.nico/lessons/482533388',
        'info_dict': {
            'id': '482533388',
            'ext': 'mp4',
            'title': '鉄道旅で学ぶ高校地理 中央本線編 ～TETSU×CHIRI 拡大版～',
            'chapter': '集う、学ぶ、ZEN Study',
            'chapter_id': '30149',
            'creators': 'count:2',
            'duration': 6208,
            'release_date': '20251015',
            'release_timestamp': 1760521790,
            'series': '★特別授業★',
            'series_id': '2361',
            'tags': 'count:1',
            'thumbnail': r're:https?://.+\.(?:jpe?g|png)',
            'timestamp': 1760522400,
            'upload_date': '20251015',
            'view_count': int,
        },
    }, {
        'url': 'https://www.nnn.ed.nico/courses/796/chapters/11752/lessons/482530901',
        'info_dict': {
            'id': '482530901',
            'ext': 'mp4',
            'title': 'ガロア理論特別講義 第1回',
            'chapter': 'ガロア理論特別講義',
            'chapter_id': '11752',
            'creators': 'count:1',
            'duration': 6441,
            'release_date': '20200629',
            'release_timestamp': 1593424190,
            'series': 'ガロア理論特別講義',
            'series_id': '796',
            'tags': 'count:2',
            'thumbnail': r're:https?://.+\.(?:jpe?g|png)',
            'timestamp': 1593424800,
            'upload_date': '20200629',
            'view_count': int,
        },
    }, {
        'url': 'https://www.nnn.ed.nico/courses/2145/chapters/27150/movie/50587',
        'info_dict': {
            'id': '50587',
            'ext': 'mp4',
            'title': 'ZEN Studyについて',
            'chapter': '【はじめに】ZEN Studyについて',
            'chapter_id': '27150',
            'duration': 443,
            'series': '【ZEN Studyの使い方】',
            'series_id': '2145',
            'tags': 'count:1',
        },
    }]

    def _real_extract(self, url):
        course_id, chapter_id, video_type, video_id = self._match_valid_url(url).group('course_id', 'chapter_id', 'type', 'id')

        if video_type == 'movie':
            video = self._call_api(
                'v2', f'{course_id}/chapters/{chapter_id}/movies/{video_id}', video_id)
            m3u8_url = traverse_obj(video, ('videos', ..., 'files', 'hls', 'url', {url_or_none}, any))
        else:
            video = self._call_api('v1', video_id, video_id)['lesson']
            m3u8_url = traverse_obj(video, ('archive', 'url', 'hls', {url_or_none}))

        if not course_id:
            course_id = traverse_obj(video, (
                'subjects', ..., 'subject_categories', ..., 'courses', ..., 'id', {str_or_none}, any))
        course_info = self._call_api('v2', course_id, course_id)

        for chapter in traverse_obj(course_info, (
            'course', 'chapters', lambda _, v: str_or_none(v['id']),
        )):
            chapter_id = traverse_obj(chapter, ('id', {str_or_none}))
            chapter_info = self._call_api('v2', f'{course_id}/chapters/{chapter_id}', chapter_id)
            if video_id in traverse_obj(chapter_info, (
                'chapter', 'class_headers', ..., 'sections', ..., 'id', {str_or_none},
            )):
                break

        return {
            'id': video_id,
            'chapter': traverse_obj(chapter_info, ('chapter', 'title', {clean_html}, filter)),
            'chapter_id': chapter_id,
            'formats': self._extract_m3u8_formats(m3u8_url, video_id, 'mp4'),
            'series': traverse_obj(course_info, ('course', 'subject_category', 'title', {clean_html}, filter)),
            'series_id': course_id,
            **traverse_obj(video, {
                'title': ('title', {clean_html}),
                'creators': ('teacher_name', {clean_html}, {lambda x: x.split('、')}, ..., {str.strip}, filter, all, filter),
                'duration': ((('archive', 'second'), 'length'), {int_or_none}, any),
                'release_timestamp': (('real_start_at', 'released_at'), {int_or_none}, any),
                'tags': ('tags', ..., {clean_html}, filter, all, filter),
                'thumbnail': (('thumbnail_wide_url', 'thumbnail_url'), {url_or_none}, any),
                'timestamp': (('planned_start_at', 'start_at'), {int_or_none}, any),
                'view_count': ('viewer_count', {int_or_none}),
            }),
        }


class ZenStudyChaptersIE(ZenStudyBaseIE):
    IE_NAME = 'zenstudy:chapters'

    _VALID_URL = r'https?://(?:www\.)?nnn\.ed\.nico/courses/(?P<course_id>\d+)/chapters/(?P<id>\d+)/?(?:[?#]|$)'
    _TESTS = [{
        'url': 'https://www.nnn.ed.nico/courses/634/chapters/20508',
        'info_dict': {
            'id': '20508',
            'title': '量子計算入門2022',
        },
        'playlist_count': 16,
    }, {
        'url': 'https://www.nnn.ed.nico/courses/490/chapters/6631',
        'info_dict': {
            'id': '6631',
            'title': '脳科学と人工知能',
        },
        'playlist_count': 7,
    }]

    def _entires(self, url, info):
        header = traverse_obj(info, (
            'class_headers', lambda _, v: v['sections'], any))
        video_type = 'movie' if header['name'] == 'section' else 'lessons'

        for section_id in traverse_obj(header, (
            'sections', ..., 'id', {str_or_none},
        )):
            yield self.url_result(
                f'{url}/{video_type}/{section_id}', ZenStudyIE)

    def _real_extract(self, url):
        course_id, chapter_id = self._match_valid_url(url).group('course_id', 'id')
        chapter_info = self._call_api('v2', f'{course_id}/chapters/{chapter_id}', chapter_id)['chapter']

        return self.playlist_result(
            self._entires(update_url(url, query=None).rstrip('/'), chapter_info),
            chapter_id, traverse_obj(chapter_info, ('title', {clean_html}, filter)))


class ZenStudyCoursesIE(ZenStudyBaseIE):
    IE_NAME = 'zenstudy:courses'

    _VALID_URL = r'https?://(?:www\.)?nnn\.ed\.nico/courses/(?P<id>\d+)/?(?:[?#]|$)'
    _TESTS = [{
        'url': 'https://www.nnn.ed.nico/courses/1068',
        'info_dict': {
            'id': '1068',
            'title': '加藤文元先生特別講義',
        },
        'playlist_count': 3,
    }]

    def _entires(self, url, info):
        for section_id in traverse_obj(info, (
            'chapters', ..., 'id', {str_or_none},
        )):
            yield self.url_result(
                f'{url}/chapters/{section_id}', ZenStudyChaptersIE)

    def _real_extract(self, url):
        course_id = self._match_id(url)
        course_info = self._call_api('v2', course_id, course_id)['course']

        return self.playlist_result(
            self._entires(update_url(url, query=None).rstrip('/'), course_info),
            course_id, traverse_obj(course_info, ('subject_category', 'title', {clean_html}, filter)))
