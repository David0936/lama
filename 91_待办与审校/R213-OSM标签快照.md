# R213：OSM 标签快照

核查日期：2026-09-14。范围为 OSM way 410417343 的公开 API 与 Overpass 标签快照；不把贡献者标签升级为官方组织或政策事实。

## 已确认

- OSM API 返回对象 `way 410417343`，版本 8，时间戳 `2024-01-21T22:12:10Z`。
- 标签含 `amenity=college`、`landuse=religious`、`religion=buddhist`、`denomination=tibetan`。
- 标签含中文、藏文、英文及其他语言名称、别名、Wikidata 与 Wikipedia 交叉字段；Overpass 快照时间为 `2026-09-14T14:11:19Z`。
- 标签中存在 `operator` 与 `operator:type` 字段，但本批不把它们当作官方文件。

## 证据边界

这是一份开放地图数据库的字段快照。它可以帮助索引多语名称、地图分类和对象版本；不能证明学院的行政性质、运营方法律地位、政策关系、招生规则、建筑用途或当前开放状态。后续使用时须保留对象 ID、版本、时间戳、许可和完整标签。

## 来源

- `S-R213-001`：OSM way JSON。
- `S-R213-002`：Overpass 标签快照。
