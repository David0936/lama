# R208：Smithsonian IIIF 对象身份

## 本批目的

核对一个海外馆藏对象的网页、IIIF manifest、馆藏号和图像权利字段，建立跨馆数字资源的最小身份卡。

## 已确认的公开材料

- Smithsonian 对象页将 `S2014.18a-b` 标为 *Padma Sambhava*，并显示 IIIF 入口。
- manifest `FS-7602_06` 的 metadata 含 accession number `S2014.18a-b`、数据源 National Museum of Asian Art、材质、尺寸、来源和展签字段。
- manifest 提供一个 canvas、图像服务和 JPEG 资源；metadata usage 标为 “Usage conditions apply”，许可链接指向 Smithsonian 使用条款。

## 证据边界

manifest 证明数字资源与馆藏号的回指关系，不证明图像可自由再发布，不替代对象页的来源研究，也不把馆方展签中的莲花生传统叙述写成独立历史事实。

## 待核

1. 为 The Met、Harvard、Walters 等对象分别核对 IIIF 或 API 的实际返回格式和权利字段。
2. 记录 manifest 版本、canvas 数量、图像服务类型和访问日期；不要只保存缩略图 URL。
3. 对同一馆藏的展览页、教育页和对象页建立资源关系，不因图片相似合并对象。

## 本批来源

- `S-R208-001`：Smithsonian 对象页与 IIIF manifest
