# 01_区域位置与地形

区域定位、山谷与地形、地名异译；地理位置与机构边界分开。

## 后续交付

以来源支持的概述、具体案例或资料卡回答本专题；每条说明适用机构、时期、群体及核查状态。事实未查到时登记缺口，不生成默认答案。

## 已登记的公开定位

- 喇荣五明佛学院位于四川省甘孜州色达县喇荣沟一带；学院自己的公开介绍将其描述为由僧尼和在家持戒者组成的佛教学习社区。这里登记的是区域级定位，不能替代测绘边界或当前行政地址（见 [学院公开介绍](https://www.larung-gar.com/)）。
- 公开地图可检索到 Larung Gar／喇荣五明佛学院的点位，但不同地图的名称、边界和更新时间并不一致。本项目暂只保留地图入口，不写入未经核对的坐标、面积或人口数字（见 [OpenStreetMap 检索](https://www.openstreetmap.org/search?query=Larung%20Gar)、[Mapcarta 地图条目](https://mapcarta.com/N4734526277)）。
- 地形、道路和建筑分布会随时期变化；后续地图卡必须注明底图日期、来源、精度和许可，不能从卫星图推断内部功能。

## R061 公开位置卡（2026-09-14）

本批把三个公开入口分成不同证据层：

| 来源 | 可登记内容 | 精度与限制 |
| --- | --- | --- |
| [University of Virginia KMaps feature 5224](https://places.kmaps.virginia.edu/features/5224) | 将 Larung Gar 标为 `religious encampment`，归入 Nyingma；点位 32.153269, 100.466955，并提供 GML、KML、Shapefile 等 GIS 下载入口 | 点位是公开地理数据库要素，不等同测绘边界；页面的海拔字段需核对单位，暂不转写为确定海拔 |
| [色达县政府区域介绍](https://www.gzzsdxrmzf.gov.cn/seda/c103068/202005/164592834550404f96cbd78c34470c27.shtml) | 介绍喇荣位于洛若镇，平均海拔约 3900 米；文中给出沟域、建筑群和建筑面积的概述 | 行政宣传页面的区域描述；面积口径、统计年份和测量方法需保留原文，不能据此画边界 |
| [高德地图检索入口](https://www.amap.com/place/B034400YZ4) | 提供“洛若镇喇荣沟”等导航检索入口，点位约 32.150521, 100.472477 | 商业导航图的检索点；与 KMaps 坐标存在差异，只作到达参考，不作为机构边界或建筑位置证据 |

KMaps 与高德的点位相距约数百米，可能来自要素中心点、检索点或底图时期差异。本项目因此只登记“区域级位置”，不计算面积、人口、建筑数量，也不把任一点视为学院大门或中心建筑。

## R109 名称字段与 GIS 下载状态（2026-09-14）

University of Virginia KMaps 的 Feature 5224 将原名字段写作 **བླ་རུང་སྒར།**，并列出 THL Simplified Tibetan Transcription 的 **Larung Gar** 与 THL Extended Wylie Transliteration 的 **bla rung sgar**。这些是该数据库的名称和转写字段，不是本地口语录音、学院官方汉文定名或所有地图服务的统一写法。

该页面链接 KML、GML、Shapefile 等 GIS 资源；本次对 KML 直链进行读取检查时获得空响应，未取得可解析几何。因此本库不生成 GeoJSON、路线或边界图，也不把“有下载链接”写成“边界数据已核”。

来源：[KMaps Feature 5224](https://places.kmaps.virginia.edu/features/5224) · [KML 资源端点](https://places.kmaps.virginia.edu/features/gis_resources/5224.kml)

## R130 三种 GIS 端点的复核状态（2026-09-14）

KMaps 特征页仍公开列出 GML、KML 与 Shapefile 三种“feature alone”下载入口。继既有 KML 复核后，本批直接读取 GML 与 Shapefile 端点，二者也未返回可解析内容。当前可以确认的是“**特征页列出三种资源端点**”；不能确认任何文件的几何类型、坐标系、边界、版本或许可。

| 端点 | 本库读取结果 | 可否建图 |
|---|---|---|
| KML | 既有 R109 记录为空响应 | 否 |
| GML | R130 读取未返回可解析内容 | 否 |
| Shapefile | R130 读取未返回可解析内容 | 否 |

来源：[KMaps Feature 5224](https://places.kmaps.virginia.edu/features/5224) · [GML端点](https://places.kmaps.virginia.edu/features/gis_resources/5224.gml) · [Shapefile端点](https://places.kmaps.virginia.edu/features/gis_resources/5224.shp)。

## 当前缺口

尚未找到一份由学院发布、带日期且可核对边界的公开总平面图。精确坐标、院寺边界、道路名称、建筑数量与当前功能均待核；历史照片或报道中的布局不自动代表今天。

## 关联

[专题目录](../README.md) · [扩编设计](../../docs/学院运转与空间扩编.md)
