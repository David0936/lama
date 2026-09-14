# 07_藏文字母数字与标点

字母、组合、数字、分节点和句读符号的识读；拼写转写与实际发音分栏。

交付时逐项附来源、适用范围与核查状态。

## 标点试样

- `་`（tsheg）通常用于藏文音节之间的分隔。
- `།`（shad）是常见的竖线标点，功能不完全等同于汉语句号。
- 组合标点、段落结尾和经文版式需按字体、文本类型和出版规范核对。

来源：[Digital Tibetan formatting rules](https://digitaltibetan.github.io/DigitalTibetan/docs/tibetan_formatting.html)

## R127｜数字排版的最小规则卡

Digital Tibetan 的技术说明面向数字文本排版。它建议换行不应切在一个音节中；一般可在音节分隔符 `་`（*tsheg*）之后换行，而 `ང་།` 被列为不应在 `་` 处分开的例外。说明还要求行首不出现 `།`（*shad*），并将 `།` 解释为类似、但不等同于逗号的藏文内部标点；诗偈、标题或较长段落末尾可用 `། །`。

| 记号／情况 | 此来源的技术说明 | 本项目使用范围 |
|---|---|---|
| `་` (*tsheg*) | 音节分隔；Unicode另有不可断行变体，用来阻止在该处换行。 | 校验网页和Markdown中的藏文断行，不充当读音或断句规则。 |
| `།` (*shad*) | 行首不应出现；用于藏文内部标点。 | 不直接替换成汉语逗号、句号或经书校勘符号。 |
| `། །` | 来源列为诗偈、标题或长段落结尾的一种排版序列，二者之间不应断行。 | 作为数字版式检查项，不认定所有版本皆用此式。 |
| `༑` (*rin chen spungs shad*) | 来源将其放在特定换行遗留音节的排版情形，并提到版本差异。 | 不在整理的转写或引文中自行补加。 |

这是一个**数字排版参考**，不是任何学院的教学规范、所有木刻版／经书的统一校勘规则，亦不提供宗教文本的释义或诵读指引。

来源定位：[Digital Tibetan formatting rules](https://digitaltibetan.github.io/DigitalTibetan/docs/tibetan_formatting.html)（Line-breaking rules、Inter-syllable marker、Usage of punctuation character *shad*、*rin chen spungs shad* 小节）。

## 待核

- 不同版本、字体、版式与经书类别的实际规范。
- 文字排版规则与口语停顿、诵读节奏之间的关系；不能从一个推出另一个。
- 数字、经名起首符和其他复合标记的独立来源与Unicode核验。

[返回专题](../README.md)
