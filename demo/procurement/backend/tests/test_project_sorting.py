import pytest

from app.database import connect, one, upsert_notice


@pytest.mark.parametrize('sort,expected', [
    (None, ['目标项目-新公告', '目标项目-旧公告', '目标项目-同秒导入']),
    ('announcement_date', ['目标项目-新公告', '目标项目-旧公告', '目标项目-同秒导入']),
    ('imported_at', ['目标项目-同秒导入', '目标项目-旧公告', '目标项目-新公告']),
])
def test_project_sorting_before_pagination_with_filters(client, sort, expected):
    with connect() as connection:
        connection.executemany(
            'INSERT INTO projects(name,purchaser,announcement_date,created_at,dataset_id) VALUES(?,?,?,?,?)',
            [
                ('目标项目-旧公告', '采购单位A', '2021-01-01', '2026-10-16 10:00:00', 'default'),
                ('目标项目-新公告', '采购单位A', '2026-10-01', '2026-10-01 10:00:00', 'default'),
                ('目标项目-同秒导入', '采购单位A', '2020-01-01', '2026-10-16 10:00:00', 'default'),
                ('不匹配搜索', '采购单位A', '2026-10-18', '2026-10-18 10:00:00', 'default'),
                ('目标项目-其他单位', '采购单位B', '2026-10-19', '2026-10-19 10:00:00', 'default'),
                ('目标项目-其他数据集', '采购单位A', '2026-10-20', '2026-10-20 10:00:00', 'other'),
            ],
        )
    params = {'q': '目标项目', 'purchaser': '采购单位A', 'page_size': 1}
    if sort is not None:
        params['sort'] = sort
    found = []
    for page in range(1, 4):
        response = client.get('/api/projects', params={**params, 'page': page})
        assert response.status_code == 200
        result = response.json()
        assert result['total'] == 3
        assert result['page'] == page
        assert len(result['data']) == 1
        found.append(result['data'][0]['name'])
    assert found == expected


def test_project_sorting_rejects_unknown_mode(client):
    assert client.get('/api/projects', params={'sort': 'unsupported'}).status_code == 422


def test_reprocessing_preserves_first_import_time(notice):
    record = notice()
    project_id = upsert_notice(record, ['notice.html'])[0]
    first_import = '2026-01-01 09:00:00'
    with connect() as connection:
        connection.execute('UPDATE projects SET created_at=? WHERE id=?', (first_import, project_id))
    record.project_name = '重新处理后的名称'
    assert upsert_notice(record, ['notice.html']) == [project_id]
    saved = one('SELECT name,created_at FROM projects WHERE id=?', (project_id,))
    assert saved == {'name': '重新处理后的名称', 'created_at': first_import}
