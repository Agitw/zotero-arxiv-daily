# ENSEMBITS 专题独立文献检索｜43 篇相关度 > 7/10

检索日：2026-10-16（Asia/Shanghai）；时间窗：2024-10-16 至 2026-10-16。种子论文不计入推荐数。

[种子论文：ENSEMBITS: an alphabet of protein conformational ensembles](https://arxiv.org/abs/2605.13789)

## 检索和评分

独立关键词检索，分结构离散化、集合生成、动力学表征三条路线；核对一手摘要、版本记录及必要的方法段落；预印本与正式版合并。相关度为本次人工判断，不是期刊质量、引用量或自动模型概率。优先最早公开日期；只有正式发表日期或首发日未核实时单独标注。

9–10：结构token与构象集合/动力学直接交叉，或单输入动态表征的紧邻方法；8–8.9：直接静态tokenizer基线、动态表征或集合生成路线；7.1–7.9：可用于评测、拓展或方法对照的近邻。严格只收录score > 7，不设篇数上限。

这是截至检索日的一次有界网络检索，不能证明穷尽全部相关文献；主要依据摘要及选定方法段落，未做全文系统综述或独立复现实验。少数论文最早公开日不确定，已明确标注。集合分布、多帧表征与有时间顺序的动力学轨迹不能等同。

## 推荐清单（按相关度降序）

### 1. From Static Structures to Ensembles: Studying and Harnessing Protein Structure Tokenization — 9.8/10

**简称：** TokenMD  
**日期：** 2025-11-13；arXiv；NeurIPS 2025 AI for Science Workshop  
**方向：** 直接邻作

研究内容：发现不同结构token可以对应近乎相同的局部几何，利用结构同义词替换扰动一个预测结构，快速生成构象集合。

推荐理由：与ENSEMBITS直接共享结构词表、单结构输入和柔性/集合建模问题；区别是利用静态词表冗余生成集合，而非学习集合自身的离散码。

[论文原文](https://arxiv.org/abs/2511.10056)

### 2. Learning protein representations with conformational dynamics — 9.7/10

**简称：** DynamicsPLM  
**日期：** 2025-10；Bioinformatics 2026；有2025预印本  
**方向：** 直接邻作

日期说明：预印本月份可核实，v1实际上线日未核实；Bioinformatics正式发表于2026-05-05。

研究内容：逐构象离散化，按残基汇聚结构token频率，形成带构象占据信息的嵌入，再用于蛋白质相互作用、定位、酶分类及金属结合预测。

推荐理由：是集合级功能表征的最直接对照：融合既有静态token的分布，而ENSEMBITS学习新的集合tokenizer。

[论文原文](https://doi.org/10.1093/bioinformatics/btag254) · [核验来源1](https://pmc.ncbi.nlm.nih.gov/articles/PMC13197115/) · [核验来源2](https://www.biorxiv.org/content/10.1101/2025.10.06.680789v1)

### 3. ProTDyn: a foundation Protein language model for Thermodynamics and Dynamics generation — 9.7/10

**简称：** ProTDyn  
**日期：** 2025-09-17；arXiv；ICLR 2026  
**方向：** 直接邻作

日期说明：按arXiv页面提交历史，不能仅从2510编号推断月份。

研究内容：用ESM3结构token统一建模平衡构象采样、多时间尺度动态轨迹及轨迹修复。

推荐理由：提供将结构离散语言用于真实动力学的直接下游框架；逐帧静态token与集合token能保留什么信息，是关键比较点。

[论文原文](https://arxiv.org/abs/2510.00013) · [核验来源1](https://openreview.net/pdf?id=fvCHkWbdgX)

### 4. Structure Language Models for Protein Conformation Generation — 9.6/10

**简称：** SLM / ESMDiff  
**日期：** 2024-10-24；ICLR 2025；arXiv  
**方向：** 直接邻作

研究内容：先用离散变分自编码器压缩结构，再条件语言建模构象分布；ESMDiff由ESM3微调并采用掩码扩散。

推荐理由：直接连接离散结构语言和构象集合生成；对照逐帧量化与直接集合编码两种路线。

[论文原文](https://arxiv.org/abs/2410.18403)

### 5. Hierarchical discrete representations for coarse-to-fine protein conformation generation — 9.5/10

**简称：** Hierarchical conformation generation  
**日期：** 2026-08-31；Bioinformatics 2026  
**方向：** 直接邻作

日期说明：可核实正式发表日期；未确认是否存在更早预印本。

研究内容：以分层VQ码本表示蛋白质结构，从粗拓扑逐步细化局部几何，评测BPTI MD和apo/holo、fold-switch构象。

推荐理由：多层离散表示与构象柔性的联系非常接近ENSEMBITS；主要区别仍是单构象分层量化和生成。

[论文原文](https://doi.org/10.1093/bioinformatics/btag611) · [核验来源1](https://academic.oup.com/bioinformatics/article/42/9/btag611/8761693) · [核验来源2](https://pubmed.ncbi.nlm.nih.gov/42599200/)

### 6. RocketSHP: Ultra-fast Proteome-scale Prediction of Protein Dynamics — 9.3/10

**简称：** RocketSHP  
**日期：** 2025-06-17；bioRxiv预印本  
**方向：** 直接邻作

研究内容：从序列或静态结构预测RMSF、运动相关性，以及基于结构量化的结构异质性谱SHP。

推荐理由：结构量化的动态摘要与单输入动力学推断均高度重叠，适合作为ENSEMBITS动态token和蒸馏分支的直接比较。

[论文原文](https://www.biorxiv.org/content/10.1101/2025.06.12.659353v1)

### 7. MD-LLM-2: A Transferable Language Model of Molecular Dynamics with Physical Conditioning and Explicit Path Probabilities — 9.3/10

**简称：** MD-LLM-2  
**日期：** 2026-10-07；arXiv预印本  
**方向：** 直接邻作

研究内容：跨mdCATH蛋白训练轨迹语言模型，以序列、温度及历史构象为条件，对结构token分布建模并赋予轨迹显式似然。

推荐理由：是本轮较新的结构token动力学模型，能帮助区分token是否仅反映构象多样性，还是能支持热力学和时间转移建模。

[论文原文](https://arxiv.org/abs/2610.10879)

### 8. MD-LLM-1: A Large Language Model for Molecular Dynamics — 9.1/10

**简称：** MD-LLM-1  
**日期：** 2025-07-21；arXiv预印本  
**方向：** 直接邻作

日期说明：arXiv页面明确提交日为7月21日，编号为2508。

研究内容：微调Mistral 7B学习蛋白质构象轨迹，在T4溶菌酶和Mad2体系探索训练未覆盖的构象状态。

推荐理由：离散结构语言用于动态构象探索的直接邻作；原文明确尚未显式建模热力学与动力学，需与后续MD-LLM-2区别。

[论文原文](https://arxiv.org/abs/2508.03709)

### 9. Learning residue level protein dynamics with multiscale Gaussians — 9.0/10

**简称：** DynaProt  
**日期：** 2025-09-01；arXiv；ICLR 2026  
**方向：** 动力学表征与预测

研究内容：由单静态结构预测每残基各向异性协方差及残基间动态耦合，并组合为全蛋白协方差来采样集合。

推荐理由：是单结构推断运动方向和相关性的强对照，可检验离散token相比连续动力学描述符的得失。

[论文原文](https://arxiv.org/abs/2509.01038)

### 10. BiHiTo: Biomolecular Hierarchy-inspired Tokenization — 9.0/10

**简称：** BiHiTo  
**日期：** 2026-03-14；AAAI 2026  
**方向：** 直接邻作

日期说明：AAAI官方页面的发表日期；存在预印本线索，更早公开日未核实。

研究内容：以Mamba和多码本量化刻画生物分子层级，覆盖从局部原子到全局构象，评测包含MD及多构象重建。

推荐理由：共享多层量化和动态构象数据，但它主要量化每个构象，而非将无序集合整体编码成token。

[论文原文](https://ojs.aaai.org/index.php/AAAI/article/view/40119)

### 11. DyProL: Dynamic Ensemble Representation Learning for Protein–Nucleic Acid Binding Site Prediction — 8.9/10

**简称：** DyProL  
**日期：** 2026-09-03；Advanced Science 2026  
**方向：** 动力学表征与预测

日期说明：正式首次在线日期；未发现并核实更早预印本。

研究内容：对BioEmu采样集合进行对齐、聚类，使用构象内及构象间几何注意力聚合，预测DNA/RNA结合位点。

推荐理由：直接检验集合表征对结合位点任务的价值；它使用连续集合特征，可与ENSEMBITS离散表示比较。

[论文原文](https://doi.org/10.1002/advs.77501) · [核验来源1](https://pubmed.ncbi.nlm.nih.gov/42693585/)

### 12. Protein Structure Tokenization: Benchmarking and New Recipe — 8.8/10

**简称：** AminoAseed / StructTokenBench  
**日期：** 2025-02-28；arXiv；ICML 2025  
**方向：** 结构tokenizer与语言模型

研究内容：建立结构tokenizer评测体系，分析码本利用率，并提出AminoAseed改善码本更新与尺寸配置。

推荐理由：直接提供静态tokenizer和下游评测对照，尤其适合判断ENSEMBITS收益来自动态信息还是更有效的量化训练。

[论文原文](https://arxiv.org/abs/2503.00089)

### 13. ESMDynamic: Fast and accurate prediction of protein dynamic contact maps from single sequences — 8.7/10

**简称：** ESMDynamic  
**日期：** 2025-08-24；Nature Communications 2026；有2025预印本  
**方向：** 动力学表征与预测

日期说明：bioRxiv v1实际Posted日期；Nature Communications正式在线2026-08-11。

研究内容：由单序列预测动态接触图，以实验多构象及MD学习接触变化和相关统计。

推荐理由：同样将昂贵动态数据压缩为廉价推理；输出是连续残基对描述，而非残基级离散集合码。

[论文原文](https://www.nature.com/articles/s41467-026-76361-2) · [核验来源1](https://www.biorxiv.org/content/10.1101/2025.08.20.671365v1)

### 14. Predicting directional flexibility in proteins — 8.7/10

**简称：** BackFlip-2  
**日期：** 2026-09-08；arXiv预印本  
**方向：** 动力学表征与预测

研究内容：SE(3)等变模型从平衡结构预测方向性骨架柔性和成对动态相关。

推荐理由：对应ENSEMBITS单结构蒸馏目标，并扩展到RMSF之外的方向和相关信息。

[论文原文](https://arxiv.org/abs/2609.08474)

### 15. DPLM: Dynamics-aware Protein Language Model via contrastive learning between sequence and molecular dynamics simulation trajectory — 8.7/10

**简称：** Dynamics-aware DPLM（非DPLM-2）  
**日期：** 2026-05-04；bioRxiv预印本  
**方向：** 动力学表征与预测

研究内容：用视频模型编码MD接触图轨迹，再通过对比学习对齐序列表征，评测柔性、突变效应、稳定性和无序区域。

推荐理由：同属把MD知识转移至可扩展蛋白表征的路线，区别是连续对比表征和序列输入。

[论文原文](https://www.biorxiv.org/content/10.64898/2026.04.29.721692v1) · [核验来源1](https://pmc.ncbi.nlm.nih.gov/articles/PMC13174341/)

### 16. When Protein Dynamics Matter: Integrating Molecular Dynamics into Protein Foundation Models — 8.5/10

**简称：** OneProt + MD  
**日期：** 2026；ICLR 2026  
**方向：** 动力学表征与预测

日期说明：已核实ICLR 2026正式论文；OpenReview首公开时间受访问验证限制，未核实到日。

研究内容：将mdCATH、GPCRmd和ATLAS轨迹经MDGen编码，作为新模态接入OneProt并做下游消融。

推荐理由：针对动力学表征何时改善功能预测给出直接证据，适合作为ENSEMBITS跨任务收益的比较框架。

[论文原文](https://openreview.net/pdf?id=Q6DuJPwH2U)

### 17. Protein Structure Tokenization via Geometric Byte Pair Encoding — 8.5/10

**简称：** GeoBPE  
**日期：** 2025-11-13；arXiv；ICLR 2026  
**方向：** 结构tokenizer与语言模型

日期说明：arXiv最早记录；可能有更早OpenReview公开稿，未核实到日。

研究内容：按几何片段逐级合并，形成可解释的多尺度结构词表，并控制重建的全局漂移。

推荐理由：是结构字母表的不同技术路线，适合比较学习式量化与几何片段词表。

[论文原文](https://arxiv.org/abs/2511.11758)

### 18. GCP-VQVAE: A Geometry-Complete Language for Protein 3D Structure — 8.5/10

**简称：** GCP-VQVAE  
**日期：** 2025-10-03；bioRxiv预印本  
**方向：** 结构tokenizer与语言模型

日期说明：bioRxiv实际Posted日期；可能有更早会议投稿公开，未确认。

研究内容：几何完整的等变编码器保留手性，再将结构量化为离散词表并解码骨架。

推荐理由：直接共享VQ-VAE结构字母表技术；几何完整性和码本利用是重要静态对照。

[论文原文](https://www.biorxiv.org/content/10.1101/2025.10.01.679833v1)

### 19. Balancing Locality and Reconstruction in Protein Structure Tokenizer — 8.5/10

**简称：** AIDO.StructureTokenizer / AIDOSt  
**日期：** 2024-12-05；bioRxiv预印本  
**方向：** 结构tokenizer与语言模型

日期说明：日期据作者PDF首页与预印本索引；bioRxiv v1直开受限。

研究内容：用VQ-VAE平衡token局部性、结构检索能力和全局重建质量。

推荐理由：直接讨论局部结构字母表应保留何种信息，可对照ENSEMBITS增加动态信息后的重建与表征权衡。

[论文原文](https://www.biorxiv.org/content/10.1101/2024.12.02.626366v1) · [核验来源1](https://www.cs.cmu.edu/~epxing/papers/2025/AIDO.ST.pdf)

### 20. Scalable emulation of protein equilibrium ensembles with generative deep learning — 8.4/10

**简称：** BioEmu  
**日期：** 2024-12-05；Science 2025；有2024预印本  
**方向：** 构象集合生成与验证

日期说明：预印本v1；Science在线2025-07-10。

研究内容：结合结构、MD与实验稳定性信息，序列条件生成平衡构象集合，学习状态相对权重。

推荐理由：为集合表征提供输入来源，也是动态知识摊销到快速推理的代表路线；本身并非离散集合tokenizer。

[论文原文](https://doi.org/10.1126/science.adv9817) · [核验来源1](https://www.biorxiv.org/content/10.1101/2024.12.05.626885v1)

### 21. ConfRover: Simultaneous Modeling of Protein Conformation and Dynamics via Autoregression — 8.4/10

**简称：** ConfRover  
**日期：** 2025-05-23；arXiv；NeurIPS 2025  
**方向：** 构象集合生成与验证

研究内容：在MD潜空间自回归建模帧间关系，结合几何扩散解码，支持独立构象及时间轨迹生成。

推荐理由：共享MD驱动的动态表征学习，但显式建模时间顺序，可补充集合token不包含的时间信息。

[论文原文](https://arxiv.org/abs/2505.17478)

### 22. Deep generative modeling of temperature-dependent structural ensembles of proteins — 8.3/10

**简称：** aSAM / aSAMt  
**日期：** 2025-03-13；Communications Chemistry 2025  
**方向：** 构象集合生成与验证

日期说明：预印本v1；Communications Chemistry正式发表于2025-11-18。

研究内容：MD训练的不变自编码器与潜扩散模型，以初始结构、序列和可选温度为条件生成重原子集合。

推荐理由：单结构到动态集合以及mdCATH学习路线高度相关，提供连续潜变量方法的对照。

[论文原文](https://www.nature.com/articles/s42004-025-01737-2) · [核验来源1](https://pmc.ncbi.nlm.nih.gov/articles/PMC11952339/)

### 23. Learning Dynamic Protein Representations at Scale with Distograms — 8.3/10

**简称：** DistoDyn  
**日期：** 2026-02-02；bioRxiv；ICLR 2026 LMRL Workshop  
**方向：** 动力学表征与预测

研究内容：利用AlphaFold2等预测器的残基距离概率分布编码动态信息，避免显式模拟或多构象采样。

推荐理由：与ENSEMBITS的动态数据稀缺问题直接对应，但用距离分布替代集合离散码。

[论文原文](https://www.biorxiv.org/content/10.64898/2026.01.29.702509v1) · [核验来源1](https://openreview.net/pdf?id=K98YJxi2Fz)

### 24. DPLM-2: A Multimodal Diffusion Protein Language Model — 8.2/10

**简称：** DPLM-2（Diffusion PLM）  
**日期：** 2024-10-17；arXiv；ICLR 2025  
**方向：** 结构tokenizer与语言模型

研究内容：通过无查表量化将坐标转成结构token，使用离散扩散联合建模蛋白序列和结构。

推荐理由：提供结构token直接下游建模框架；主要处理单构象，可比较换用动态表征的可能价值。

[论文原文](https://arxiv.org/abs/2410.13782)

### 25. Bio2Token: All-atom tokenization of any biomolecular structure with Mamba — 8.0/10

**简称：** Bio2Token  
**日期：** 2024-10-24；arXiv预印本  
**方向：** 结构tokenizer与语言模型

研究内容：使用Mamba编解码与有限标量量化，对蛋白质、核酸和小分子的全原子结构进行离散压缩。

推荐理由：可对照结构词表的可扩展性与原子分辨率，但不直接汇聚构象集合。

[论文原文](https://arxiv.org/abs/2410.19110)

### 26. Learning to engineer protein flexibility — 8.0/10

**简称：** Flexpert  
**日期：** 2024-12-24；arXiv；ICLR 2025  
**方向：** 动力学表征与预测

研究内容：从序列或序列加结构预测MD残基RMSF，并将柔性预测用于引导蛋白设计。

推荐理由：是ENSEMBITS RMSF评测和单输入动态预测的直接任务基线。

[论文原文](https://arxiv.org/abs/2412.18275)

### 27. Flexibility-Conditioned Protein Structure Design with Flow Matching — 8.0/10

**简称：** BackFlip / FliPS  
**日期：** 2025-06-29；arXiv；ICML 2025  
**方向：** 动力学表征与预测

日期说明：按arXiv页面提交日期，编号为2508。

研究内容：BackFlip从骨架预测残基柔性，FliPS以柔性profile为条件进行流匹配骨架设计。

推荐理由：对应单结构动态描述符预测，并给出动力学表征用于设计的具体用途。

[论文原文](https://arxiv.org/abs/2508.18211)

### 28. Adaptive Protein Tokenization — 8.0/10

**简称：** APT  
**日期：** 2026-02-06；arXiv预印本  
**方向：** 结构tokenizer与语言模型

研究内容：采用逐token增加细节的全局结构表示，支持自适应压缩和不同长度的结构编码。

推荐理由：探索局部残基token之外的表示方式，适合比较集合编码的压缩率与信息组织。

[论文原文](https://arxiv.org/abs/2602.06418)

### 29. Yeti: A compact protein structure tokenizer for reconstruction and multi-modal generation — 8.0/10

**简称：** Yeti  
**日期：** 2026-05-11；arXiv预印本  
**方向：** 结构tokenizer与语言模型

研究内容：结合无查表量化与流匹配训练，兼顾词表利用、结构重建和多模态生成。

推荐理由：较新的静态tokenizer基线，可对照量化训练与下游生成能力。

[论文原文](https://arxiv.org/abs/2605.09981)

### 30. Flow-Matching-Based Protein Structure Tokenizer Made Efficient and Easy — 8.0/10

**简称：** ProFiT  
**日期：** 2026-09-27；arXiv预印本  
**方向：** 结构tokenizer与语言模型

研究内容：用轻量流匹配结构tokenizer简化训练，并关注码本利用、数据效率和跨任务迁移。

推荐理由：与ENSEMBITS的数据效率及词表语义问题有关，是本轮较新的静态对照。

[论文原文](https://arxiv.org/abs/2609.33129)

### 31. Aligning Protein Conformation Ensemble Generation with Physical Feedback — 8.0/10

**简称：** Energy-based Alignment / EBA  
**日期：** 2025-05-30；arXiv；ICML 2025  
**方向：** 构象集合生成与验证

研究内容：用物理能量反馈对齐集合生成器，校准不同构象状态的相对权重。

推荐理由：有助于评估集合token是否保留生物物理相关的状态差异；重点是分布校准而非离散编码。

[论文原文](https://arxiv.org/abs/2505.24203)

### 32. From Possibility to Precision in Macromolecular Ensemble Prediction — 8.0/10

**简称：** Perspective：集合表征与验证  
**日期：** 2025-05-03；Perspective；Nature Methods 2026  
**方向：** 综述与观点

日期说明：arXiv首发；Nature Methods正式在线2026-05-18。

研究内容：讨论真实集合数据、统一集合编码、跨实验整合与集合专属验证标准的缺口。

推荐理由：直接对应ENSEMBITS的表征目标及验证难点，适合用来设计超越RMSF的评测。

[论文原文](https://arxiv.org/abs/2505.01919) · [核验来源1](https://doi.org/10.1038/s41592-026-03084-z)

### 33. Pi-Ensemble: Sequence-guided generation of interpolated protein conformational ensembles — 7.8/10

**简称：** Pi-Ensemble  
**日期：** 2026-08-15；bioRxiv预印本  
**方向：** 构象集合生成与验证

研究内容：交替使用逆折叠与结构预测，在两个锚定状态之间提出中间构象，无需重新训练。

推荐理由：可提供有针对性的构象集合以测试动态token；与集合量化的技术重合有限。

[论文原文](https://www.biorxiv.org/content/10.64898/2026.08.12.744498v1)

### 34. UniFlow: Unifying protein conformational ensemble generation and machine-learned force fields with a scalable normalizing Flow — 7.8/10

**简称：** UniFlow  
**日期：** 2026-07-20；bioRxiv预印本  
**方向：** 构象集合生成与验证

研究内容：内部坐标归一化流同时支持独立集合采样、精确似然与可微能量/力计算。

推荐理由：提供统一集合分布和动力学的连续表示路线，适合作为动态表征保留物理信息的参照。

[论文原文](https://www.biorxiv.org/content/10.64898/2026.07.17.739266v1)

### 35. Comparison of AI protein structure ensemble prediction tools — 7.8/10

**简称：** 集合生成器比较  
**日期：** 2026-05-30；bioRxiv预印本  
**方向：** 构象集合生成与验证

研究内容：比较BioEmu、AFsample2及ESMFlow，发现其生成分布差异显著，对突变引发的状态变化也存在不足。

推荐理由：直接关系到用预测集合训练或评测ENSEMBITS时的输入偏差；构象多样性不等同于正确平衡权重。

[论文原文](https://www.biorxiv.org/content/10.64898/2026.05.29.728804v1)

### 36. Rectifying AI-generated protein structure ensembles for equilibrium using physics-based computations — 7.8/10

**简称：** WE-RW集合校正  
**日期：** 2026-04-03；bioRxiv预印本  
**方向：** 构象集合生成与验证

研究内容：以AI集合初始化加权集合模拟，再通过RiteWeight重加权，恢复给定力场下较一致的平衡集合。

推荐理由：用于思考集合token训练目标是否应显式考虑构象权重和物理校正。

[论文原文](https://www.biorxiv.org/content/10.64898/2026.03.24.714034v1)

### 37. Learning Structure, Energy, and Dynamics: A Survey of Artificial Intelligence for Protein Dynamics — 7.8/10

**简称：** AI蛋白质动力学综述  
**日期：** 2026-04-28；arXiv综述预印本  
**方向：** 综述与观点

研究内容：整理构象集合生成、轨迹生成、Boltzmann生成器、物理约束、粗粒化与集体变量发现。

推荐理由：提供动力学建模的总体定位，但覆盖面比ENSEMBITS的集合token化更广。

[论文原文](https://arxiv.org/abs/2604.25244)

### 38. PEGASUS: Prediction of MD-derived protein flexibility from sequence — 7.5/10

**简称：** PEGASUS  
**日期：** 2025-07-16；期刊论文2025  
**方向：** 动力学表征与预测

日期说明：已核实期刊在线日期；未找到并核实更早预印本。

研究内容：由蛋白语言模型序列表征预测ATLAS中的RMSF、主链二面角波动等MD柔性指标。

推荐理由：适合作为动态信息预测的序列基线，方法上不涉及集合tokenizer。

[论文原文](https://pmc.ncbi.nlm.nih.gov/articles/PMC12267886/)

### 39. Learning millisecond protein dynamics from what is missing in NMR spectra — 7.5/10

**简称：** Dyna-1  
**日期：** 2025-03；Nature 2026；有2025预印本  
**方向：** 动力学表征与预测

日期说明：预印本月份可核实，v1实际Posted日未完成一手核验；Nature在线2026-08-10。

研究内容：从NMR缺失指认学习微秒至毫秒交换信号，借助蛋白模型预测逐残基动态倾向。

推荐理由：可补充短MD轨迹之外的实验时间尺度检验，检验动态token的泛化边界。

[论文原文](https://www.nature.com/articles/s41586-026-10989-4) · [核验来源1](https://doi.org/10.1101/2025.03.19.642801)

### 40. Learning Latent Protein Languages for Autoregressive Generation — 7.5/10

**简称：** SLL  
**日期：** 2026-10-02；arXiv预印本  
**方向：** 结构tokenizer与语言模型

研究内容：在几何结构量化基础上加入序列和置信度监督，学习用于自回归生成的潜在蛋白语言。

推荐理由：对应结构词表的语义和语言模型用途，未直接建模无序构象集合。

[论文原文](https://arxiv.org/abs/2610.03978)

### 41. Atom-level Protein Representation Learning Improves Protein Structure Prediction — 7.5/10

**简称：** TriProRep  
**日期：** 2026-05-21；arXiv预印本  
**方向：** 结构tokenizer与语言模型

研究内容：联合氨基酸、骨架和全原子局部几何视图，对结构视图VQ量化并进行受扰动token恢复预训练。

推荐理由：提供更细粒度局部结构token的对照，但主要侧重结构而非动态信息。

[论文原文](https://arxiv.org/abs/2605.22133)

### 42. AFsample3: Generating and selecting multiple conformational states with Alphafold3 — 7.5/10

**简称：** AFsample3  
**日期：** 2026-01-17；bioRxiv预印本  
**方向：** 构象集合生成与验证

研究内容：扩展AlphaFold3采样并选择多种构象状态，在实验多状态蛋白上评测替代构象覆盖。

推荐理由：是预测集合输入来源的较新方法，可用来测试集合token对生成器偏差的敏感性。

[论文原文](https://www.biorxiv.org/content/10.64898/2026.01.16.699904v1)

### 43. From static structures to dynamic landscapes: Generative artificial intelligence for protein conformational dynamics — 7.5/10

**简称：** 生成式动力学综述  
**日期：** 2026-06；Current Opinion in Structural Biology综述2026  
**方向：** 综述与观点

日期说明：期刊卷期日期；更早在线或预印本日期未核实。

研究内容：综述从静态预测走向构象分布、配体响应集合和路径推断的生成式方法及局限。

推荐理由：为集合词表所服务的生成与应用场景提供近期背景，技术重合度低于直接邻作。

[论文原文](https://www.sciencedirect.com/science/article/pii/S0959440X26000618)

## 排除与版本去重记录

- [ENSEMBITS: an alphabet of protein conformational ensembles](https://arxiv.org/abs/2605.13789)：用户提供的种子论文，不重复算作新推荐。
- [SeqDance: A Protein Language Model for Representing Protein Dynamic Properties](https://www.biorxiv.org/content/10.1101/2024.10.11.617911v1)：首发2024-10-15，比窗口起点早一天；即使高度相关也排除。
- [Simulating 500 million years of evolution with a language model（ESM3）](https://www.evolutionaryscale.ai/blog/esm3-release)：2024年6/7月已公开；Science 2025正式发表不重置首发日期。
- [AlphaFold Meets Flow Matching for Generating Protein Ensembles（AlphaFlow / ESMFlow）](https://arxiv.org/abs/2402.04845)：首发2024-02-07，窗口外。
- [Improving AlphaFlow for Efficient Protein Ensembles Generation（AlphaFlow-Lit）](https://arxiv.org/abs/2407.12053)：首发2024-07，窗口外。
- [Generative Modeling of Molecular Dynamics Trajectories（MDGen）](https://arxiv.org/abs/2409.17808)：首发2024-09，窗口外。
- [ProToken / Unifying sequence-structure coding for advanced protein engineering via a multimodal diffusion transformer](https://pubs.rsc.org/en/content/articlepdf/2025/sc/d5sc02055g)：2025正式版有2023 tokenizer预印本前身；本轮按版本去重，未完成新增内容的全文比对，不当作全新tokenizer计入。
- [Tokenized and continuous embedding compressions of protein sequence and structure（CHEAP）](https://doi.org/10.1016/j.patter.2025.101289)：预印本2024-08，窗口外；Patterns 2025不重置首发。
- [FoldToken 1–4](https://github.com/A4Bio/FoldToken_open)：已核实作者仓库所列首次公开均在2024年3–8月，窗口外。
- [mdCATH: A Large-Scale MD Dataset for Data-Driven Computational Biophysics](https://arxiv.org/abs/2407.14794)：首发2024-07，窗口外；未查到独立mdCATH-div新论文，不把数据划分名当论文。
- [MISATO: machine learning dataset of protein–ligand complexes for structure-based drug discovery](https://doi.org/10.1038/s43588-024-00627-2)：2024-05已发表，窗口外。
- [Inferring dynamic information from protein structures by Gaussian integrals and deep learning](https://doi.org/10.1093/bioinformatics/btag446)：本次相关度7.0，仅预测较粗全蛋白动态量；不满足严格大于7。

## 主要检索式

- `protein structure tokenizer dynamics ensemble 2025 2026`
- `protein dynamics representation learning molecular dynamics foundation model RMSF`
- `protein conformational ensemble discrete tokens language model`
- `protein structure tokenizer VQ-VAE LFQ FSQ geometric byte pair encoding`
- `predict protein dynamics single structure flexibility`
- `protein ensemble generation thermodynamics dynamics language model`
- `mdCATH-div MISATO ATLAS representation`
- `MD-LLM protein structural tokens`
- `dynamic ensemble representation protein function binding site`

## 本次推送

本次为独立专题，发送到项目已有收件配置。主题相关度来自本次检索人工评估，不借用Zotero兴趣分、期刊加分或日常推荐排名；不设top-N截断。SMTP接受状态另记录于CODEX_STATE.md和GitHub Actions运行日志。
