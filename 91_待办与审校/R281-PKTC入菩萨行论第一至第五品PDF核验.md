# R281｜PKTC《入菩萨行论》第一至第五品 PDF 文件核验

## 记录目的

把 PKTC 页面列出的五个公开 PDF 从“入口目录”提升为文件级记录：保存直接 URL、页数、字节数、SHA-256 和文本层抽样状态。文件均为根本文本与英文讲解合刊，不当作藏汉双语定本。

## 来源与文件结果

页面总入口：[Entering the Conduct of a Bodhisatva](https://pktc.org/shantideva-entering-conduct-bodhisatva-bodhicaryavatara/)。页面第 69—89 行列出两种藏文电子版及第一至第五品文件；第 23—40 行的版权说明要求私人分发边界。

| 直接 PDF | 页面品次 | 页数 | 字节数 | SHA-256 | 抽样结果 |
|---|---:|---:|---:|---|---|
| <https://pktc.org/wp-content/themes/bb-theme-child/downloads/bca1comm.pdf> | 1 | 585 | 2,423,969 | `0e1a882bb03883ad650c2c58683276ab5c44d7cd919a74142cd1e8f083327f34` | pypdf 前 3 页有文本 |
| <https://pktc.org/wp-content/themes/bb-theme-child/downloads/bca2comm.pdf> | 2 | 331 | 1,292,135 | `21f8476fc55bcc95bf10bd809f080cfccf36e876f32e8904b381dc0d81a5f83a` | pypdf 前 3 页有文本 |
| <https://pktc.org/wp-content/themes/bb-theme-child/downloads/bca3comm.pdf> | 3 | 158 | 623,535 | `edcb89ee52c6cd636868f9abe3d1e21d8ba50eca9973caf75b32aef89d4bfc20` | pypdf 前 3 页有文本 |
| <https://pktc.org/wp-content/themes/bb-theme-child/downloads/bca4comm.pdf> | 4 | 192 | 729,808 | `0cf817c7d2ed617813d1e2ad54c4f822b35890a64121e4adf38b4186891e0a10` | pypdf 前 3 页有文本 |
| <https://pktc.org/wp-content/themes/bb-theme-child/downloads/bca5comm.pdf> | 5 | 290 | 1,115,774 | `1e9663f844b7edba7d4c630ca3bfc673de77f32c07b1ef90bff898636743f6c` | pypdf 前 3 页有文本 |

核验日期：2026-09-15。下载文件存于临时目录，核验后删除；仓库不保存 PDF 本体。

## 页面明确的文本与传承信息

- 第 1 品文件封面标为 Khenpo Kunpal commentary，含根本文与英文讲解；文件版权页注明 Andreas Kretschmar（2003）版权。
- PKTC 页面把第一至第五品分别描述为菩提心利益、忏悔、受持菩提心、谨慎和内省，并说明英文材料仍有未完成部分。
- 第 1 品 PDF 导言称作品传统归于印度僧人寂天，并说明藏传宁玛、噶举、萨迦、旧噶当与新噶当等解释线均有相关传统；这些是该文件导言的历史／传统叙述，不替代现代校勘。

## 边界

- 文件状态：`download_verified`；只表示本次读取的文件指纹和抽样文本。
- 权利状态：`copyright_restricted`；不把“免费电子版”写成 Public Domain 或可再托管。
- 未完成：藏文根本文本的逐页 OCR／校勘、汉文版本取得、藏汉逐句对应和喇荣学院课程指定版本确认。
