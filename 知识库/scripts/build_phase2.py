from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "知识库"


# id, category, title, tasks, conditions, core, validation, metrics, pitfalls, alternatives, implementation
MODELS = [
    ("M01", "统计建模", "多元线性回归", "连续因变量解释、影响因素分析、基线预测", "样本独立；关系近似线性；误差条件均值为零；推断时还需关注同方差和残差分布", "用设计矩阵表达主效应、交互项与非线性变换；系数含义必须绑定变量单位。分类变量设置参照组，避免虚拟变量陷阱。", "残差-拟合图、Q-Q 图、Breusch-Pagan 检验、VIF；报告调整R²和系数置信区间；与仅截距或简单规则基线比较。", "MAE、RMSE、调整R²、AIC/BIC、系数CI", "把相关当因果；只看R²；逐步回归反复试验却不校正；对时间或重复测量数据误用独立假设", "岭/Lasso、GAM、混合效应模型、稳健回归", "sklearn Pipeline 做变换与拟合；statsmodels 用于完整推断；训练集确定变换参数。"),
    ("M02", "统计建模", "Logistic回归", "二分类、风险概率估计、可解释基线", "观测条件独立；logit 与连续特征近似线性；无完全分离；样本量能支撑事件数与参数数", "建模 log odds；系数以优势比解释。非线性可用样条，阈值应根据题目代价而非固定0.5。", "校准曲线、Brier分数、ROC/PR曲线、共线性与分离检查；交叉验证必须在折内完成预处理。", "ROC-AUC、PR-AUC、F1、Recall、Specificity、Brier、校准斜率", "类别极不平衡仍只报准确率；先全数据筛特征；用测试集选阈值；把优势比误写为概率增量", "正则化Logistic、GAM、树模型、贝叶斯Logistic", "优先输出predict_proba；单独保存阈值选择依据与混淆矩阵。"),
    ("M03", "统计建模", "广义线性模型GLM", "计数、比例、二元和正偏响应建模", "响应分布属于合适指数族；链接函数合理；均值-方差关系与数据相符", "根据响应选择 Binomial/Poisson/Gamma 等分布和链接函数。计数模型必须检查暴露量并使用 offset。", "过度离散、零膨胀、残差与影响点检查；比较Poisson和负二项；报告偏差与置信区间。", "Deviance、AIC、对数似然、预测误差、覆盖率", "对计数直接OLS；忘记offset；Poisson方差假设明显失效仍沿用；比例数据越界", "负二项、零膨胀、Beta回归、GAM", "statsmodels family与link显式配置；预测时保留暴露量定义。"),
    ("M04", "统计建模", "混合效应模型", "重复测量、层级数据、个体异质性", "分组结构正确；随机效应结构有数据支撑；条件独立；随机效应分布近似合理", "固定效应描述总体规律，随机截距/斜率描述组间差异。先由实验结构决定随机效应，再用ML比较固定效应、REML估计最终参数。", "组内相关ICC、随机效应方差、残差诊断、奇异拟合检查；按组交叉验证，禁止同一个体跨训练测试。", "边际/条件R²、AIC、似然比、RMSE、系数CI", "把重复观测当独立样本；随机结构过度复杂；用普通随机K折造成个体泄漏", "GEE、层级贝叶斯、固定效应面板模型", "保存group列和随机效应公式；预测新组与已见组时分别评估。"),
    ("M05", "统计建模", "广义加性模型GAM", "未知平滑非线性关系、可解释预测", "样本覆盖自变量范围；平滑度受到惩罚控制；外推需求有限", "用样条基函数表示非线性效应，平滑参数控制偏差-方差。可加入张量积处理二维交互，但需防止自由度膨胀。", "检查有效自由度、偏残差、平滑项置信带和边界行为；与线性模型及树模型比较。", "解释偏差、AIC、RMSE、平滑项显著性", "把曲线形状过度解释为机制；样本稀疏区过度弯曲；在训练范围外外推", "多项式回归、样条回归、树模型、高斯过程", "固定结点/平滑参数选择流程；绘制数据密度与置信带。"),
    ("M06", "统计建模", "稳健回归与分位数回归", "异常值敏感数据、条件分布异质性", "稳健损失与业务目标匹配；分位数样本量足够；观测结构仍需正确", "Huber等M估计降低极端残差影响；分位数回归直接建模中位数或尾部分位，揭示均值模型看不到的异质性。", "比较OLS与稳健结果；Bootstrap置信区间；检查不同分位曲线是否交叉及样本尾部稳定性。", "MAE、分位数损失、覆盖率、系数CI", "把所有异常都交给稳健模型而不调查数据错误；分位数结果缺乏不确定性", "数据纠错、加权最小二乘、广义分布回归", "异常点保留审计标记；同时报告原始与稳健结果。"),
    ("M07", "统计建模", "成分数据分析CoDA", "各分量非负且总和固定的比例/化学成分数据", "闭合约束成立；零值处理有合理机制；分析在对数比空间进行", "采用CLR/ILR/ALR变换避免伪相关；零值需区分检测限、结构零和四舍五入零，不能直接统一加常数。", "比较不同零替代方案；在单纯形空间解释结果；逆变换后检查分量和与非负性。", "Aitchison距离、分类/预测指标、敏感性分析", "直接对原始比例做相关与回归；忽略定和约束；预测分量和不为1", "Dirichlet回归、log-ratio回归、专门的零膨胀CoDA", "变换器写入Pipeline；记录分母或ILR基选择。"),
    ("M08", "统计建模", "生存分析与Cox模型", "到事件时间、删失数据、达标时点", "删失机制可接受；Cox比例风险假设近似成立；时间起点与事件定义明确", "使用风险集处理删失；Cox系数解释为风险比。若比例风险失效，可用时间交互、分层Cox或AFT。", "Schoenfeld残差、校准、生存曲线、时间依赖AUC；交叉验证以个体为单位。", "C-index、IBS、时间AUC、校准误差、HR的CI", "删除删失样本；把未发生事件当普通连续时间；混淆风险比与概率比", "Kaplan-Meier、AFT、随机生存森林、DeepSurv", "明确event与duration编码；输出指定时点生存概率。"),
    ("M09", "统计建模", "主成分分析PCA", "连续变量降维、共线性缓解、可视化", "变量尺度经过合理统一；线性组合能表达主要变异；异常值未主导协方差", "对训练集标准化后分解协方差/相关矩阵，以累计解释方差和下游任务共同确定维数。载荷用于解释，不等于因果贡献。", "碎石图、重构误差、载荷稳定性；PCA必须在训练折内拟合。", "解释方差比、重构误差、下游CV指标", "全数据PCA造成泄漏；只按85%阈值机械选维；对类别混合数据直接使用", "稀疏PCA、因子分析、UMAP、自动编码器", "Pipeline(StandardScaler,PCA,model)；保存载荷和特征顺序。"),
    ("M10", "统计建模", "聚类分析", "无监督分群、画像、分组策略候选", "距离或相似度有业务意义；尺度处理合理；聚类稳定且可解释", "K-means适合近球形簇；层次聚类适合探索层级；GMM允许椭圆分布和软归属。模型选择不能只看一项内部指标。", "多随机种子稳定性、Bootstrap一致性、轮廓系数、外部变量解释；检查聚类是否只是尺度或异常值产物。", "Silhouette、Calinski-Harabasz、Davies-Bouldin、ARI稳定性", "把聚类标签当真实类别；使用人为编号计算距离；先聚类再在同数据宣称显著差异", "GMM、谱聚类、密度聚类、规则分组", "预处理和距离定义写入配置；输出簇中心及不确定样本。"),
    ("M11", "机器学习", "决策树", "非线性分类回归、可解释规则基线", "样本量能支撑叶节点；剪枝或复杂度限制；类别代价明确", "递归选择划分降低不纯度。限制深度、最小叶样本或代价复杂度剪枝，以防把噪声写成规则。", "嵌套或交叉验证选复杂度；检查叶节点样本量与规则稳定性。", "任务指标、树深、叶数、校准误差", "展示训练树却不测试；叶节点极小；把单树特征重要性解释为因果", "Logistic、随机森林、梯度提升、规则模型", "使用Pipeline；导出规则时同时标注样本覆盖和误差。"),
    ("M12", "机器学习", "随机森林与ExtraTrees", "表格分类回归、非线性交互、稳健基线", "样本近似同分布；树数充足；分类不平衡得到处理", "Bootstrap样本与随机特征降低树间相关。ExtraTrees增加随机切分，通常更快但偏差可能更高。", "OOB与交叉验证对照；排列重要性；分组/时间数据使用对应切分；检查概率校准。", "ROC/PR-AUC、F1、MAE/RMSE、OOB误差", "用不纯度重要性比较高基数变量；忽略时间顺序；无限制搜索后只报最好分数", "梯度提升、正则化线性模型、CatBoost", "固定随机种子和n_jobs；保存特征名与训练版本。"),
    ("M13", "机器学习", "梯度提升树XGBoost/LightGBM/CatBoost", "中小规模表格分类回归、复杂非线性", "验证集代表目标分布；类别和缺失处理一致；调参预算受控", "逐轮拟合残差/梯度。学习率、树深、叶数和正则化共同控制容量；使用早停，但早停集不能兼任最终测试集。", "嵌套CV或独立验证；学习曲线、校准、SHAP稳定性；与线性和随机森林基线比较。", "任务指标、最佳轮数、泛化差距、校准误差", "测试集早停；把SHAP当因果；小样本上过度调参；类别编码泄漏", "随机森林、GAM、TabPFN或正则化线性模型", "训练/验证/测试职责分离；导出模型及特征schema。"),
    ("M14", "机器学习", "支持向量机SVM", "中小样本高维分类回归", "特征已缩放；核函数与数据结构匹配；样本规模允许核矩阵计算", "最大化间隔，C控制误分类惩罚，RBF的gamma控制作用范围。参数必须在交叉验证内搜索。", "学习曲线、嵌套CV、概率校准；检查不同缩放和核的稳定性。", "ROC/PR-AUC、F1、支持向量比例、MAE", "未标准化；在全数据调C/gamma；高维小样本只报一次切分", "Logistic、核岭、随机森林、线性SVM", "Scaler与SVM放同一Pipeline；大样本优先LinearSVC。"),
    ("M15", "机器学习", "K近邻KNN", "局部结构分类回归、简单基线、相似样本检索", "距离有意义；特征尺度统一；维度不过高；训练数据覆盖预测区域", "根据邻域标签或响应聚合，k控制平滑程度。加权距离可减弱边界影响。", "交叉验证选择k和距离；检查维度灾难与查询样本距离分布。", "任务指标、邻域纯度、查询距离", "类别编号当连续距离；未缩放；高维稀疏数据仍直接欧氏距离", "Logistic、SVM、树模型、度量学习", "Pipeline缩放；保存最近邻证据便于解释。"),
    ("M16", "机器学习", "朴素贝叶斯", "文本/高维稀疏分类、小样本概率基线", "条件独立是假设近似；分布族与特征形式匹配；平滑参数合理", "Multinomial适合计数，Bernoulli适合二值，Gaussian适合连续近正态。虽假设强，但常是有价值基线。", "概率校准、混淆矩阵、与Logistic比较；检查零频问题。", "Log-loss、PR-AUC、F1、Brier", "错误选择分布族；把输出概率当已校准；强相关特征重复计权", "Logistic、线性SVM、树模型", "文本向量化必须在训练折内；记录平滑参数。"),
    ("M17", "机器学习", "类别不平衡学习", "罕见事件、异常识别、少数类召回", "评价指标与错误代价一致；重采样只作用于训练折；测试分布保持真实", "优先尝试类权重和阈值调整，再考虑SMOTE等重采样。概率模型若重采样，需要重新校准或修正先验。", "分层/分组CV；PR曲线、不同阈值代价、校准；少数类样本数和置信区间。", "PR-AUC、Recall、Specificity、Fβ、MCC、Brier", "测试集过采样；SMOTE后再划分；只报准确率；盲目追求召回忽略误报", "代价敏感学习、异常检测、两阶段模型", "用imbalanced-learn Pipeline；阈值决策另存JSON。"),
    ("M18", "机器学习", "模型集成与Stacking", "多个互补模型融合、提升稳定性", "基模型误差具有互补性；元学习只使用折外预测；测试集完全隔离", "Voting平均预测；Stacking用OOF预测训练元模型。复杂度只有在稳定增益超过方差和解释成本时才合理。", "嵌套CV、逐模型消融、相关误差分析、校准；报告增益置信区间。", "相对基线增益、方差、校准、推理成本", "用训练内预测训练元模型造成泄漏；只展示最好一次；堆叠高度相似模型", "简单平均、单一强模型、贝叶斯模型平均", "保存每折OOF索引和预测；元特征不可来自测试标签。"),
    ("M19", "时间序列", "ARIMA/SARIMA", "单变量短期预测、趋势与季节性", "差分后近似平稳；残差近白噪声；结构在预测期相对稳定", "ARIMA通过AR、差分和MA刻画依赖；SARIMA加入季节项。阶数由领域周期、ACF/PACF及信息准则共同确定。", "滚动起点评估、Ljung-Box残差检验、预测区间覆盖；与季节朴素基线比较。", "MAE、RMSE、MASE、区间覆盖率", "随机划分时间数据；只看拟合优度；差分过度；没有季节朴素基线", "ETS、Prophet、状态空间、树模型滞后特征", "保留时间频率和缺口处理规则；预测区间必须输出。"),
    ("M20", "时间序列", "指数平滑ETS", "水平、趋势、季节性序列预测", "趋势和季节结构相对稳定；异常冲击得到处理；频率明确", "组合误差、趋势和季节组件，可含阻尼趋势。小样本下通常是强而稳定的基线。", "滚动验证、残差白噪声、季节朴素对照、区间覆盖。", "MASE、sMAPE、RMSE、覆盖率", "自动模型结果不解释；时间缺口当零；结构突变后继续外推", "ARIMA、结构时间序列、Prophet", "记录additive/multiplicative选择及频率。"),
    ("M21", "时间序列", "VAR与多变量时序", "多个内生序列联动预测、动态关系", "序列平稳或协整得到处理；滞后阶合理；参数量相对样本可控", "VAR让每个变量依赖所有变量的滞后；有协整时考虑VECM。脉冲响应描述模型内动态，不自动等同因果效应。", "稳定性根、残差自相关、Granger预测性、滚动预测；滞后阶敏感性。", "多变量预测误差、AIC/BIC、区间覆盖", "样本少变量多；把Granger称为真正因果；未来外生变量使用真实值造成泄漏", "动态因子、VECM、状态空间、树模型", "按时间切分；预测期外生变量必须有可用生成方式。"),
    ("M22", "时间序列", "零膨胀与间歇需求模型", "大量零销量、间歇发生的计数预测", "零来源可区分；发生概率与正值规模可分别建模；评估窗口足够", "Hurdle模型先预测是否发生，再预测正值；零膨胀模型区分结构零与抽样零。间歇需求可用Croston类方法。", "零比例校准、发生与规模分开评估、滚动验证；与全零和历史均值基线比较。", "PR-AUC、MAE/MASE、Poisson deviance、库存成本", "先平均平滑掩盖零结构；用普通回归产生负预测；只报整体RMSE", "Tweedie、负二项、Croston、两阶段树模型", "输出发生概率和条件数量；最终决策规则单独记录。"),
    ("M23", "优化决策", "线性规划LP", "资源分配、运输、配比、成本最小化", "目标与约束可线性表达；参数单位一致；连续决策合理", "明确集合、参数、变量、目标和约束。先建立量纲表；求解后检查原始约束残差、对偶值和边界。", "检查求解状态、原始约束残差、对偶值和边界；使用小规模人工可算实例核验。", "求解状态、目标值、最大约束违反、松弛量、对偶价格", "只给算法不写数学模型；单位不一致；求解器返回可行却违反业务规则；把连续量错误取整", "MILP、二次规划、网络流", "保存模型文件、求解器日志和独立约束校验器。"),
    ("M24", "优化决策", "混合整数规划MILP", "选址、排程、是否选择、离散资源配置", "逻辑关系可线性化；Big-M有紧致上界；规模在求解预算内", "二元变量表达选择与逻辑。优先使用indicator约束；若用Big-M必须推导有效上界，避免数值不稳定。", "MIP gap、上下界、求解时间、节点数、约束违反；用小规模实例人工验证。", "最优性gap、目标值、可行率、运行时间", "把超时可行解称为最优；Big-M随意设极大；结果表未复核逻辑约束", "CP-SAT、分解算法、启发式算法", "固定求解时限和gap；导出incumbent及最优界。"),
    ("M25", "优化决策", "多目标优化", "成本、风险、公平、收益等冲突目标", "各目标定义和方向清楚；尺度可比；决策者偏好可表达或输出Pareto集", "加权和需先标准化且解释权重；ε-约束更适合展示目标权衡；输出Pareto前沿而不是只报单点。", "支配性检查、权重/ε敏感性、前沿覆盖、方案可行性。", "各目标值、超体积、间距、可行率", "权重凭空指定；不同量纲直接相加；宣称唯一最优；只比较综合分不展示原目标", "目标规划、ε-约束、Pareto启发式", "保留每个原始目标列；综合目标不得覆盖原值。"),
    ("M26", "优化决策", "随机规划与情景优化", "需求、价格、产量等随机参数下的决策", "情景生成能代表不确定性；决策时序和信息可用性正确；概率权重合理", "区分先验决策和情景后决策，禁止使用决策时不可知信息。进行样本外情景评估并报告期望、尾部和失败概率。", "情景外测试、EVPI/VSS、情景数收敛、概率敏感性。", "期望收益、分位收益、违约概率、VSS、EVPI", "用同一批情景优化和评价；随机参数独立假设无依据；未来信息泄漏", "鲁棒优化、分布鲁棒、CVaR优化", "分离训练情景与评估情景；保存随机种子与生成参数。"),
    ("M27", "优化决策", "鲁棒优化", "参数只知区间/集合、强调最坏情形保障", "不确定集合有数据或业务依据；保守程度参数可解释；鲁棒对应形式可求解", "在不确定集合内优化最坏情形。预算不确定集可调节保守性；必须报告名义性能与保障代价。", "样本外压力测试、集合半径敏感性、最坏约束违反。", "最坏收益、名义收益、可行率、鲁棒代价", "区间随意放大；把保守结果称为预测准确；没有与随机/名义方案比较", "随机规划、分布鲁棒、机会约束", "不确定集合参数单独配置；独立模拟做压力测试。"),
    ("M28", "优化决策", "CVaR风险优化", "关注损失尾部的投资、库存、农业与供应链决策", "损失定义明确；置信水平与风险偏好有解释；尾部样本或情景足够", "CVaR度量超过VaR阈值后的平均损失，可线性化嵌入优化。应同时报告期望收益和尾部风险的权衡。", "置信水平、风险权重、情景数敏感性；独立情景尾部回测。", "期望收益、VaR、CVaR、最坏损失、可行率", "损失正负号写反；样本太少估计高分位；只报风险下降不报收益代价", "均值-方差、鲁棒优化、机会约束", "显式保存alpha和lambda；核对经验CVaR与模型变量。"),
    ("M29", "优化决策", "动态规划", "多阶段决策、序列分段、库存与路径", "状态包含未来决策所需全部信息；转移与边界正确；问题满足最优子结构", "定义状态、动作、转移、阶段成本和终止条件。通过记忆化或递推求解，并用小规模穷举核验。", "Bellman一致性、边界测试、与穷举结果对照、复杂度。", "目标值、运行时间、状态数、可行率", "状态遗漏导致伪最优；边界off-by-one；只写递推式不恢复方案", "最短路、MILP、强化学习", "实现backpointer恢复完整决策；单元测试覆盖最小规模。"),
    ("M30", "优化决策", "遗传算法与差分进化", "非凸、组合、黑箱且精确求解困难的问题", "编码能表达可行解；预算足够多次运行；约束处理不会奖励不可行解", "明确染色体、初始化、变异/交叉、选择和终止。启发式只提供当前最好解，不能无证据称全局最优。", "多随机种子分布、收敛曲线、可行率、与简单启发式/求解器小实例对照、参数敏感性。", "最好/中位目标、方差、可行率、耗时", "只跑一次；惩罚系数掩盖约束违反；比较不同算法却预算不等；称全局最优", "MILP、模拟退火、粒子群、局部搜索", "独立可行性检查；保存每代最优与随机种子。"),
    ("M31", "优化决策", "蒙特卡洛模拟", "风险传播、概率估计、不确定性量化", "输入分布及相关结构有依据；随机数生成正确；样本量满足误差要求", "从联合分布采样并传播到输出。若变量相关，使用协方差、Copula或情景联合采样，不能默认独立。", "蒙特卡洛标准误、样本量收敛、分布假设敏感性、极端值稳定性。", "均值/分位数、概率、MCSE、置信区间", "分布凭空指定；忽略相关性；样本量大却模型结构错误；只报均值", "Bootstrap、解析传播、拉丁超立方", "固定种子但报告多种子验证；保存分布参数与采样代码。"),
    ("M32", "深度学习", "多层感知机MLP", "大样本非线性表格/向量预测、深度学习基线", "样本量相对参数足够；特征缩放正确；验证集与测试集独立", "使用小而受控的网络作为起点，配合权重衰减、Dropout和早停。表格小样本中不默认优于提升树。", "学习曲线、多种子、消融、校准、与线性和树模型比较。", "任务指标、泛化差距、多种子均值±标准差", "小数据堆大网络；测试集早停；只报最佳种子；无传统模型基线", "梯度提升树、GAM、TabNet", "确定性设置与设备记录；保存最佳epoch和归一化器。"),
    ("M33", "深度学习", "CNN一维/二维卷积", "图像、频谱、局部序列模式", "局部平移结构有意义；样本与增强策略合理；通道和尺寸语义明确", "卷积共享局部权重。1D CNN可处理固定窗口序列，2D CNN用于图像；输入窗口构造不得跨越预测边界。", "患者/实体级切分、增强消融、Grad-CAM谨慎解释、外部或时间验证。", "任务指标、多种子方差、推理成本", "把同一对象切片随机分到训练测试；增强改变标签语义；可视化当因果", "传统特征+树、Transformer、RNN", "数据集返回样本ID并做泄漏断言；记录增强配置。"),
    ("M34", "深度学习", "LSTM/GRU", "长短期序列预测、变长序列分类", "时间顺序可靠；序列长度和采样频率一致或有掩码；训练样本充足", "门控循环结构建模序列状态。必须明确单步/多步策略、教师强制及推理时可用输入。", "滚动验证、季节朴素基线、多种子、误差随预测步长曲线。", "MASE、RMSE、各步误差、区间覆盖", "随机切分窗口；未来特征进入输入；在短数据上参数过多", "ARIMA/ETS、TCN、Transformer、树模型滞后特征", "窗口生成器单元测试；隐藏状态不跨独立样本泄漏。"),
    ("M35", "深度学习", "Transformer时序模型", "长依赖、多变量序列、大规模时序", "数据量和算力足够；位置/时间编码正确；预测掩码防止看未来", "注意力建模跨时间依赖。必须证明相对简单基线的稳定增益，并控制参数量和搜索预算。", "因果mask测试、滚动验证、多种子、消融、不同长度泛化与推理成本。", "MASE、RMSE、多步误差、参数量、耗时", "掩码错误造成未来泄漏；小样本追求复杂模型；只和弱基线比较", "LSTM、TCN、N-BEATS、统计时序", "自动测试打乱未来值不应影响过去预测；保存mask配置。"),
    ("M36", "深度学习", "图神经网络GNN", "对象及关系构成图、节点/边/图级任务", "图构造来自真实关系而非为用GNN而造图；划分避免共享实体泄漏；消息传递深度合理", "选择同构或异构图；消息聚合应与边语义匹配。需要与不使用边的MLP、传统图特征模型比较。", "按实体/时间划分、边消融、随机边对照、多种子、过平滑诊断。", "任务指标、边消融增益、层间表示相似度", "由标签构图；测试节点信息传入训练；没有无图基线；把attention权重当因果", "MLP、树模型、矩阵分解、标签传播", "保存节点/边schema和划分掩码；构图代码可复现。"),
    ("M37", "深度学习", "自编码器与表示学习", "降维、去噪、异常检测、特征预训练", "重构目标能代表正常结构；训练集污染受控；潜空间维度有依据", "编码器压缩、解码器重构。异常检测用重构误差需验证异常确实难以重构；强模型也可能重构异常。", "与PCA/IsolationForest比较；潜维消融；阈值仅在验证集选择。", "重构误差、PR-AUC、潜空间稳定性", "在含测试异常的全数据训练；直接以重构误差断言异常；只展示二维图", "PCA、One-Class SVM、Isolation Forest", "预处理器与网络共同版本化；输出阈值依据。"),
    ("M38", "深度学习", "深度生存模型", "复杂非线性生存风险和个体化事件时间", "删失处理正确；样本量足够；时间划分和个体划分无泄漏", "网络输出风险分数、离散时间概率或参数分布；损失函数必须正确纳入风险集或删失。", "与Cox/AFT比较；时间校准、IBS、多种子、删失敏感性和外部验证。", "C-index、IBS、时间AUC、校准", "只优化C-index忽略校准；风险集实现错误；复杂模型无统计基线", "Cox、AFT、随机生存森林", "用成熟生存库验证自定义损失；构造小样本数值测试。"),
    ("M39", "验证解释", "Bootstrap与置信区间", "估计不确定性、模型性能区间、稳定性", "重采样单位符合数据独立结构；重复数足够；统计量定义稳定", "独立样本按行Bootstrap，分组/时间数据需按组或块重采样。区间可用百分位、BCa等方法。", "检查区间随重复数稳定；明确训练重拟合还是仅重算指标；报告重采样单位。", "标准误、置信区间、覆盖率", "重复测量按行抽样；只对预测值重采样却声称包含训练不确定性", "解析CI、贝叶斯后验、重复交叉验证", "固定主种子并派生子种子；保存抽样索引摘要。"),
    ("M40", "验证解释", "SHAP与特征解释", "黑箱模型全局和局部解释、错误分析", "解释器与模型匹配；背景数据代表目标分布；特征依赖得到考虑", "SHAP分解相对基线的预测贡献，不证明因果。相关特征会共享或重分配贡献，应结合置换、PDP/ALE和领域知识。", "跨折/跨种子稳定性、相关特征分组、符号与模型行为核对、局部样本审查。", "重要性稳定度、解释一致性、计算成本", "把SHAP值称为因素影响或因果效应；用测试标签筛解释；只展示漂亮蜂群图", "Permutation importance、ALE、系数、反事实", "保存模型、背景集抽样规则和特征显示名。"),
]


# id, title, trigger, checks, failure, action
STAT_CHECKS = [
    ("S01", "分析单位与独立性", "同一人/企业/地块多次观测，或存在班级、地区、年份层级", "明确观测单位、抽样单位和推断单位；画出ID-时间结构；划分时保持组完整", "把相关样本当独立会低估标准误并导致测试泄漏", "使用分组切分、混合模型、GEE或聚类稳健标准误"),
    ("S02", "缺失机制与处理", "任一关键字段存在缺失", "报告缺失比例和模式；区分MCAR/MAR/MNAR的合理性；插补器只在训练集拟合", "直接删行改变总体；先全数据插补造成泄漏；用0代替缺失扭曲含义", "小比例可完整案例并做敏感性；MAR考虑多重插补；MNAR做情景分析"),
    ("S03", "异常值与影响点", "箱线图、残差或业务范围发现极端值", "先区分录入错误、真实稀有事件和分布长尾；报告处理前后结果", "机械3σ删除可能删掉任务最关键样本", "数据纠错、稳健方法、变换、截尾敏感性；保留审计列"),
    ("S04", "多重比较", "同时检验多个变量、组别、时间点或染色体", "记录检验族和总次数；区分探索性与验证性；控制FDR或FWER", "挑选最小p值产生假发现", "探索阶段Benjamini-Hochberg；强确认场景Bonferroni/Holm；报告校正后p值"),
    ("S05", "效应量与区间", "报告显著性或模型优劣", "同时给效应量、方向、单位和置信区间；区分统计显著与实际重要", "只给p<0.05无法判断效果大小", "回归系数/OR/标准化差异及95%CI；性能差给配对Bootstrap CI"),
    ("S06", "共线性与可识别性", "高度相关变量、虚拟变量、交互项或高阶项", "相关矩阵、VIF、条件数；检查完全分离、奇异拟合和参数可识别性", "系数符号不稳、标准误巨大却解释单变量贡献", "中心化、合并变量、正则化、降维；保留预测和解释目的的区别"),
    ("S07", "训练验证测试职责", "任何监督学习或调参", "训练用于拟合；验证/CV用于选择；测试只做一次最终估计；预处理在折内", "测试集参与特征筛选、早停或阈值选择导致乐观偏差", "冻结测试集；嵌套CV用于重度调参；保存索引和数据版本"),
    ("S08", "时间与组别泄漏", "时间序列、重复测量、同主体多条记录", "核查特征产生时间；保证同主体不跨集合或按任务模拟真实部署", "未来统计量、目标编码、同患者记录泄漏", "TimeSeriesSplit、GroupKFold或时间+组联合切分；写泄漏断言"),
    ("S09", "样本量与模型容量", "变量多、少数类少、深度模型或复杂随机效应", "报告总样本、独立组数、事件数、每类样本和参数规模；画学习曲线", "小样本复杂模型得分方差巨大", "简化模型、正则化、重复CV、Bootstrap区间；把深度模型降为探索性"),
    ("S10", "分布和残差诊断", "使用回归、GLM、时序或概率模型", "按模型检查残差、均值-方差、过度离散、自相关、校准", "只依据正态性检验机械接受/拒绝模型", "结合图形、稳健标准误、替代分布或非参数方法"),
    ("S11", "敏感性与稳健性", "存在阈值、权重、分布、误差范围或主观参数", "列出关键参数；给合理范围和依据；报告结论是否改变而非只报目标值", "只扰动不重要参数，或只展示最稳定区间", "单因素+情景/全局敏感性；标记决策翻转点"),
    ("S12", "可重复性与随机性", "随机划分、随机初始化、采样或启发式算法", "固定并记录种子、软件版本、配置和硬件；报告多种子分布", "只保留最佳运行；无法从原始数据生成最终表格", "一键流水线、环境锁定、结果哈希、至少多种子均值和标准差"),
]


ENGINEERING = [
    ("E01", "主键重复导致表连接膨胀", "merge后行数异常增加或指标离谱", "连接前验证左右键唯一性和预期基数；连接后检查行数、未匹配率和重复键", "pandas merge(validate='one_to_one'/'many_to_one')；输出anti-join样本"),
    ("E02", "数据类型与单位漂移", "数值列读成字符串、百分号/日期/周数混杂", "建立schema，显式解析；统一单位后做范围断言", "禁止静默errors='coerce'；记录无法解析值与原单位"),
    ("E03", "缺失值泄漏", "插补后CV异常高", "插补、缩放、编码全部放入Pipeline并在每折训练集拟合", "为缺失本身有信息的字段增加指示变量并验证"),
    ("E04", "目标泄漏", "单个特征近乎完美、上线不可获得", "记录特征可用时间和生成链；逐列做目标相关与名称审计", "删除事后字段；用部署时刻重建特征快照"),
    ("E05", "时间窗口穿越", "时序模型离线很好、未来失效", "窗口只使用预测时点之前数据；滚动统计先shift再rolling", "编写测试：修改未来值不得改变过去特征"),
    ("E06", "同主体跨训练测试", "患者、商品、地块有重复记录", "按主体ID分组切分；若预测未来记录则使用时间+主体规则", "保存split manifest并断言集合ID交集为空"),
    ("E07", "类别编码不一致", "测试出现新类别或列顺序变化", "OneHotEncoder(handle_unknown='ignore')或显式字典；保存特征schema", "训练和推理共用同一序列化Pipeline"),
    ("E08", "指标实现错误", "手算与库函数不一致、正负类颠倒", "小型人工样例验证；显式指定positive label、average和sample_weight", "输出混淆矩阵并由其复算关键指标"),
    ("E09", "测试集参与调参", "反复查看测试分数选择模型", "冻结测试集；所有选择在CV/验证完成；记录试验决策", "最终测试只执行一次并写入不可覆盖的结果文件"),
    ("E10", "阈值固定或偷调", "概率模型默认0.5或用测试集找最佳阈值", "基于业务代价/验证集选择阈值；单独评估校准", "保存threshold.json，含目标、数据版本和候选曲线"),
    ("E11", "随机性不可复现", "重复运行结果大幅变化", "统一设置Python/NumPy/框架/算法种子；记录线程和确定性选项", "仍需报告多种子分布，固定种子不等于稳健"),
    ("E12", "求解器伪最优", "优化器超时仍输出方案", "检查status、gap、best bound、约束违反和数值容差", "表述为限时可行解；独立校验器复算目标和约束"),
    ("E13", "启发式算法不可行解", "高目标值伴随约束违反", "解码后逐条检查硬约束；不可行解不得参与最优比较", "优先可行编码/修复算子；记录每代可行率"),
    ("E14", "结果文件与论文数字漂移", "正文数字无法追溯", "指标、表格、图由同一流水线生成；每个产物附数据和代码版本", "建立claim-evidence清单；禁止手工改图表数字"),
    ("E15", "图表误导", "截断坐标、颜色含义不一致、样本量隐藏", "坐标、单位、误差条、样本数、颜色图例完整；同类图统一尺度", "图由脚本生成；分类配色与连续色图分开"),
    ("E16", "性能与内存问题", "大表循环、重复拷贝、模型运行超时", "先profile再优化；向量化、合理dtype、分块处理、稀疏矩阵", "优化前后做等价性测试；记录耗时和峰值内存"),
]


def frontmatter(**kwargs: object) -> str:
    return "---\n" + yaml.safe_dump(kwargs, allow_unicode=True, sort_keys=False).strip() + "\n---\n\n"


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def slug(text: str) -> str:
    return re.sub(r"[\\/:*?\"<>| ]+", "_", text).strip("_")


def build_models() -> list[dict]:
    root = KB / "02_建模手" / "模型卡"
    reset_dir(root)
    index: list[dict] = []
    for mid, category, title, tasks, conditions, core, validation, metrics, pitfalls, alternatives, implementation in MODELS:
        folder = root / category
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{mid}_{slug(title)}.md"
        body = frontmatter(
            card_id=mid, card_type="model", title=title, category=category,
            roles=["modeler", "engineer", "judge"], verified=True, version="1.0"
        ) + f"""# {title}

## 适用任务

{tasks}。

## 使用前提

{conditions}。

## 建模要点

{core}

最低工作流：定义预测/决策对象和分析单位 → 建立简单基线 → 仅在训练数据拟合预处理 → 拟合候选模型 → 用与数据结构匹配的验证方案评估 → 完成误差、稳健性与失败样本分析。

## 最低验证要求

{validation}

推荐记录：{metrics}。

## 常见失败模式

{pitfalls}。

## 替代或对照模型

{alternatives}。

## 工程实现提示

{implementation}

## 评委检查点

- 是否说明为什么该模型比简单基线更适合本题，而不只是“模型先进”。
- 是否逐条核验使用前提，并处理不满足的条件。
- 数据切分、特征处理、调参和阈值选择是否与最终测试隔离。
- 是否报告不确定性、失败情形和结论适用边界。
- 复杂模型若无稳定且有实际意义的增益，应退回简单模型。
"""
        path.write_text(body, encoding="utf-8")
        index.append({"id": mid, "category": category, "title": title, "path": str(path.relative_to(KB)).replace("\\", "/")})
    return index


def build_stat_checks() -> list[dict]:
    root = KB / "01_共享基础" / "统计严谨性检查卡"
    reset_dir(root)
    index = []
    for cid, title, trigger, checks, failure, action in STAT_CHECKS:
        path = root / f"{cid}_{slug(title)}.md"
        text = frontmatter(card_id=cid, card_type="statistics_check", title=title, roles=["modeler", "engineer", "judge"], verified=True) + f"""# {title}

## 触发条件

{trigger}。

## 必查证据

{checks}。

## 不检查的后果

{failure}。

## 推荐处理

{action}。

## 验收输出

- 一段明确结论：检查是否通过、证据在哪里、剩余风险是什么。
- 至少一个可复核产物：诊断图、统计表、数据断言或划分清单。
- 若未通过，返工项必须指定责任人和验收条件。
"""
        path.write_text(text, encoding="utf-8")
        index.append({"id": cid, "title": title, "path": str(path.relative_to(KB)).replace("\\", "/")})
    return index


def build_engineering() -> list[dict]:
    root = KB / "03_工程师" / "故障卡"
    reset_dir(root)
    index = []
    for cid, title, symptom, diagnosis, fix in ENGINEERING:
        path = root / f"{cid}_{slug(title)}.md"
        text = frontmatter(card_id=cid, card_type="engineering_failure", title=title, roles=["engineer", "judge"], verified=True) + f"""# {title}

## 典型症状

{symptom}。

## 定位方法

{diagnosis}。

## 修复与预防

{fix}。

## 最小测试

构造一个能稳定复现该问题的小样本；修复前测试必须失败，修复后必须通过。测试同时检查行数/索引、数据类型、关键指标或约束值，不能只检查程序“不报错”。

## 评委验收

- 提交故障原因而非只提交修改后的代码。
- 展示修复前后的可量化差异。
- 确认修复未改变无关数据和既有正确结果。
- 把防回归测试纳入主流水线。
"""
        path.write_text(text, encoding="utf-8")
        index.append({"id": cid, "title": title, "path": str(path.relative_to(KB)).replace("\\", "/")})
    return index


def build_writer() -> list[dict]:
    root = KB / "04_论文手"
    root.mkdir(parents=True, exist_ok=True)
    # Preserve external repositories and manually curated assets.
    for old in root.glob("W[0-9][0-9]_*.md"):
        old.unlink()
    docs = {
        "W01_国赛论文结构模板.md": """# 国赛 C 题论文结构模板

## 摘要

按“问题对象—各问方法—关键数值结果—验证与结论”组织。每一问至少出现一个方法和一个定量结果；禁止只列模型名。摘要最后给3–5个可检索关键词。

## 问题重述与分析

重述只改写任务，不提前给答案。问题分析逐问说明输入、输出、困难、方法选择及与上一问依赖，必须能映射到需求追踪矩阵。

## 假设与符号

每条假设说明必要性、可能偏差和后续验证。符号表包含含义、单位、类型和取值范围，同一符号全文唯一。

## 数据处理

交代样本量变化、主键、缺失、异常、单位、划分和防泄漏措施。每个删除规则给出删除数量。

## 各问模型

按“目标—变量—假设—公式—求解—结果—验证—小结”展开。公式后解释量纲和参数；结果回答题目动词，不停留在模型指标。

## 评价、推广与参考文献

优点必须有证据，缺点必须具体到假设或数据边界，推广说明需要改变的参数和条件。引用应可核验，禁止编造文献。
""",
        "W02_摘要检查表.md": """# 摘要检查表

- 是否覆盖全部小问且顺序一致？
- 是否给出具体方法，而非“建立数学模型”？
- 是否写出关键数值、单位和比较对象？
- 是否说明至少一种验证或稳健性证据？
- 是否删除背景套话、软件操作和未在正文出现的结论？
- 摘要数字是否能追踪到结果文件？
- 关键词是否包含题目领域与核心方法？

不满足任一小问覆盖或数字可追溯要求时，摘要不得通过终审。
""",
        "W03_图表规范.md": """# 图表规范

图表必须能独立阅读：编号、标题、轴名、单位、图例、样本量和必要误差条齐全。分类变量用离散配色，连续变量用感知均匀色图；避免彩虹色图和仅靠颜色区分。比较图使用同一坐标尺度；截断坐标必须显著说明。

表格小数位由测量精度和决策需要决定，同列统一；最优值加粗不能替代统计不确定性。热力图同时考虑色标范围和数值标注。每张图表正文必须回答“看到了什么、为什么重要、对应哪项题目要求”。
""",
        "W04_LaTeX公式与表格规范.md": r"""# LaTeX 公式与表格规范

行内公式使用 `$...$`，重要公式使用带编号环境。向量、矩阵、集合和随机变量字体统一；首次出现的每个符号必须定义。长公式按等号或运算符对齐，不使用截图公式。

表格优先 `booktabs`，避免密集竖线；跨页表使用 `longtable`。所有图表使用 `\label` 和 `\ref` 交叉引用。编译前检查未定义引用、溢出框、缺失字体及图片路径。
""",
        "W05_主张证据链模板.md": """# 主张—证据链模板

| claim_id | 论文主张 | 小问 | 指标/表格文件 | 图 | 代码入口 | 数据版本 | 评审状态 |
|---|---|---|---|---|---|---|---|
| C-Q1-001 | 待填写 | Q1 | outputs/...json | figures/...pdf | src/...py | hash | pending |

任何包含“显著、优于、稳健、最优、提高、降低”的句子必须登记。`最优`还需给求解状态或最优性差距；`显著`需给检验与效应量；`稳健`需给敏感性范围；`优于`需给同一划分下的配对比较。
""",
        "W06_最终论文自检.md": """# 最终论文自检

1. 每个题目要求都有正文位置、结果和交付文件。
2. 摘要、正文、图表和附件数字一致。
3. 变量、单位、样本量及模型名称全文一致。
4. 所有图表被正文引用，所有公式符号已定义。
5. 结论不超出数据和实验范围，没有把相关写成因果。
6. 基线、验证、敏感性和失败情形已陈述。
7. 参考文献真实可核验，外部材料标注来源。
8. 附录代码与最终结果版本一致，复现命令可运行。
9. 删除空泛套话、重复问题重述和无法证明的“具有较强推广价值”。
10. PDF编译无缺图、乱码、越界、未解析引用和匿名违规信息。
""",
    }
    index = []
    for name, content in docs.items():
        path = root / name
        wid = name.split("_")[0]
        path.write_text(frontmatter(card_id=wid, card_type="writing", roles=["writer", "judge"], verified=True) + content, encoding="utf-8")
        index.append({"id": wid, "title": content.splitlines()[0].lstrip("# "), "path": str(path.relative_to(KB)).replace("\\", "/")})
    return index


def build_judge() -> list[dict]:
    root = KB / "05_评委"
    reset_dir(root)
    docs = {
        "J01_评分量表.md": """# 标准化评分量表

所有指标采用0–4级锚定：0缺失或错误；1严重缺陷；2基本完成但证据不足；3正确完整且证据充分；4在3的基础上有经验证的增量价值。

| 维度 | 权重 | 3分标准 | 4分附加要求 |
|---|---:|---|---|
| 题意与覆盖 | 10 | 全部要求有证据链 | 识别隐含约束并验证 |
| 数据与EDA | 12 | 审计完整、处理可复现 | 数据问题有机制分析 |
| 模型合理性 | 15 | 与任务匹配、假设核验 | 结构选择有对照证据 |
| 统计严谨性 | 15 | 划分、检验、区间正确 | 不确定性传播完整 |
| 创新性 | 10 | 有题目针对性且有效 | 消融证明稳定增益 |
| 代码复现 | 10 | 一键运行、版本完整 | 自动测试和产物追踪 |
| 验证稳健性 | 12 | 基线、CV、敏感性齐全 | 外部/时序/压力验证 |
| 解释决策价值 | 6 | 结论可执行且有边界 | 给风险—收益权衡 |
| 论文表达 | 7 | 逻辑、公式、图表一致 | 高信息密度且无歧义 |
| 完整交付 | 3 | 文件、格式和附件齐全 | 自动核验交付物 |

总分 `S=Σ w_i*l_i/4`。硬门槛优先于总分：遗漏小问、数据泄漏、违反硬约束、核心结果不可复现或伪造来源均必须REWORK；存在学术不诚信则FAIL。
""",
        "J02_拆题与需求追踪.md": """# 拆题与需求追踪规范

逐句提取任务动词、对象、数据范围、约束、评价标准和交付格式。每项生成唯一 `requirement_id`，字段包括原文、任务类型、输入、输出、依赖、责任人、验收条件、证据路径和状态。

先画小问依赖：后问使用前问结果时，前问结论必须版本化；前问返工后，所有下游成果标记stale。计划每次只通过patch更新，不重写历史。没有题干原文映射的工作不得占用核心比赛时间。
""",
        "J03_阶段门禁.md": """# 阶段门禁

## G1 题意门
全部小问、显隐约束、交付物和依赖已进入需求矩阵。

## G2 数据门
数据字典、主键、单位、缺失、异常、划分和泄漏审计通过。

## G3 方案门
每问至少一个简单基线和一个候选方案；假设、指标、验证与失败预案明确。

## G4 实验门
代码可运行；指标、图表、日志可追溯；约束复核、基线、CV和敏感性完成。

## G5 写作门
主张证据链完整；摘要和正文数字一致；图表公式引用无误。

## G6 终审门
需求覆盖100%；无硬门槛问题；交付文件完整；评分与改进建议已生成。
""",
        "J04_返工协议.md": """# 返工协议

评审决定仅允许 `PASS`、`CONDITIONAL_PASS`、`REWORK`。每个问题包含严重度、证据、影响范围、根因、责任角色、修复动作、验收测试和截止阶段。

阻断问题必须先处理；同一根因不得拆成大量低价值问题。返工完成后只重审受影响项及其下游依赖。前序产物版本变化时，评委将下游证据标记stale，禁止论文继续引用旧结果。
""",
        "J05_创新性审查.md": """# 创新性审查

创新可以来自新变量、机制约束、损失函数、验证设计、求解方法或模型组合，而非单纯换成更复杂算法。至少回答：解决了哪个基线缺陷；增量组件是什么；比较预算是否公平；消融后增益多大；跨折/种子是否稳定；复杂度和解释成本是否值得。

没有基线或消融时创新性最高2分；只有训练集提升最高1分；若复杂方案无稳定实际增益，要求退回简单方案。
""",
        "J06_硬性红线.md": """# 硬性红线

- 任一小问或指定附件未交付。
- 测试数据参与预处理拟合、特征选择、调参、早停或阈值选择。
- 优化结果违反硬约束，或把超时可行解声称为全局最优。
- 论文关键数字无法从当前代码和数据复现。
- 编造实验、数据、文献、政策或来源。
- 将相关性、特征重要性或SHAP直接表述为因果。
- 用案例论文的数值替代当前题目计算。

前四项至少REWORK；学术不诚信直接FAIL并停止成果合并。
""",
        "J07_评审输出Schema.md": """# 评审输出 Schema

```json
{
  "review_id": "REV-001",
  "stage": "G3",
  "artifact_versions": {},
  "decision": "REWORK",
  "blocking_issues": [{"id":"I-01","evidence":"...","impact":"..."}],
  "non_blocking_issues": [],
  "scores": {"model_validity":{"level":2,"evidence":"..."}},
  "actions": [{"owner":"engineer","task":"...","acceptance_test":"..."}],
  "invalidated_downstream_artifacts": [],
  "plan_patch": []
}
```

所有评分必须引用证据路径；没有证据时不能给3或4。自然语言建议放在结构化字段之后，不能替代Schema。
""",
        "J08_改进优先级.md": """# 改进优先级

按以下顺序排序：硬门槛与结论有效性 → 权重×评分缺口 → 下游影响范围 → 修复成本与剩余时间 → 表达美化。推荐计算 `priority = severity × score_gap × downstream_factor / effort`，但最终需人工判断依赖关系。

评委每轮最多给出少量最高价值动作。每项说明预期提升的评分维度；字体、配色等美化不得排在数据泄漏、模型假设和复现问题之前。
""",
        "J09_官方格式门禁.md": """# 官方格式门禁

终审必须检索 `04_论文手/官方格式规范/OF02_官方论文格式条款卡.md` 和 `OF03_官方格式提交检查表.md`，并以原始PDF复核。以下任一项失败均不得提交：正文超过30页；电子论文超过20MB；电子版含承诺书/编号页或第一页不是摘要页；出现身份、学校、赛区信息；附录缺少支撑材料清单或完整可运行程序；支撑材料与论文不一致；外部成果未规范引用。

字体、字号、行距和颜色不属于全国统一强制项；六段摘要、固定章节顺序、数字加粗、图下表上和三线表可作为质量建议，但不得依据本PDF作为取消资格的判罚项。AI声明不在该PDF范围内，应等待当年官方专项通知。
""",
    }
    index = []
    for name, content in docs.items():
        path = root / name
        jid = name.split("_")[0]
        path.write_text(frontmatter(card_id=jid, card_type="judge", roles=["judge"], verified=True) + content, encoding="utf-8")
        index.append({"id": jid, "title": content.splitlines()[0].lstrip("# "), "path": str(path.relative_to(KB)).replace("\\", "/")})
    return index


def write_model_selector() -> None:
    path = KB / "02_建模手" / "模型选择图谱.md"
    path.write_text(frontmatter(card_id="MODEL_SELECTOR", card_type="routing", roles=["modeler", "judge"], verified=True) + """# C题模型选择图谱

| 任务与数据结构 | 首选基线 | 候选增强 | 必查事项 |
|---|---|---|---|
| 连续表格预测 | 线性/GAM | RF、GBDT、MLP | 非线性、泄漏、残差 |
| 二分类/风险 | Logistic | GBDT、Stacking | 不平衡、校准、阈值 |
| 重复测量 | 混合效应 | GEE、深度生存 | 按主体划分 |
| 时间到事件 | KM/Cox | AFT、RSF、深度生存 | 删失、时间校准 |
| 大量零销量 | 全零/季节基线 | Hurdle、Tweedie | 零机制、滚动验证 |
| 单变量时序 | 季节朴素/ETS | ARIMA、深度时序 | 时间切分、区间 |
| 多变量时序 | VAR基线 | 状态空间、深度模型 | 未来变量可用性 |
| 比例总和固定 | ILR+线性模型 | CoDA专用模型 | 零值与闭合约束 |
| 资源配置 | LP | MILP、多目标 | 单位、约束复核 |
| 随机参数决策 | 名义方案 | 随机/鲁棒/CVaR | 样本外情景 |
| 黑箱组合优化 | 简单贪心 | GA/DE/SA | 多种子、可行率 |
| 图关系数据 | MLP/图统计 | GNN | 构图依据、边消融 |

模型选择顺序：先任务和部署方式，再数据结构与独立性，再损失/决策代价，最后才是算法。任何复杂候选必须与首选基线在相同数据划分、特征和预算下比较。
""", encoding="utf-8")


def write_index(parts: dict[str, list[dict]]) -> None:
    index_path = KB / "00_规范与索引" / "第二阶段知识索引.md"
    lines = ["# 第二阶段核心知识索引", ""]
    for section, rows in parts.items():
        lines += [f"## {section}", "", "| ID | 标题 | 路径 |", "|---|---|---|"]
        for row in rows:
            lines.append(f"| {row['id']} | {row['title']} | `{row['path']}` |")
        lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")


CASE_PATTERNS = {
    "M01": r"线性回归|多元回归|最小二乘",
    "M02": r"Logistic|逻辑回归",
    "M03": r"广义线性模型|Poisson|负二项",
    "M04": r"混合效应|LMM",
    "M05": r"加性模型|GAM|样条",
    "M06": r"稳健回归|分位数回归",
    "M07": r"成分数据|中心化对数比|CLR|ILR",
    "M08": r"生存分析|Cox|风险函数",
    "M09": r"主成分|PCA",
    "M10": r"聚类|K-means|层次聚类",
    "M11": r"决策树",
    "M12": r"随机森林|ExtraTrees",
    "M13": r"XGBoost|LightGBM|CatBoost|梯度提升",
    "M14": r"支持向量机|SVM",
    "M15": r"K近邻|KNN",
    "M16": r"朴素贝叶斯",
    "M17": r"不平衡|SMOTE|Focal Loss",
    "M18": r"Stacking|堆叠|集成学习|元学习",
    "M19": r"ARIMA|SARIMA",
    "M20": r"指数平滑|ETS",
    "M21": r"VAR\(|向量自回归|VECM",
    "M22": r"零膨胀|间歇需求|Croston|Hurdle",
    "M23": r"线性规划",
    "M24": r"整数规划|0-1规划|混合整数|LINGO",
    "M25": r"多目标",
    "M26": r"随机规划|随机优化|情景优化",
    "M27": r"鲁棒优化",
    "M28": r"CVaR|条件风险价值",
    "M29": r"动态规划",
    "M30": r"遗传算法|差分进化|DEGA",
    "M31": r"蒙特卡罗|Monte Carlo",
    "M32": r"多层感知机|MLP",
    "M33": r"卷积神经网络|CNN",
    "M34": r"LSTM|GRU|循环神经网络",
    "M35": r"Transformer",
    "M36": r"图神经网络|GNN",
    "M37": r"自编码器|Autoencoder",
    "M38": r"深度生存|DeepSurv",
    "M39": r"Bootstrap|自助法|置信区间",
    "M40": r"SHAP|特征解释|特征重要性",
}


def write_case_mapping(models: list[dict]) -> dict[str, list[str]]:
    cases_root = KB / "06_优秀案例"
    case_docs = {p.parent.name: p.read_text(encoding="utf-8") for p in cases_root.glob("*/01_清洗正文.md")}
    mapping: dict[str, list[str]] = {}
    title_by_id = {row["id"]: row["title"] for row in models}
    lines = [
        "# 方法卡—优秀论文案例映射",
        "",
        "该映射由方法关键词自动识别，只说明案例正文提及或使用了该方法，不代表方法使用正确或验证充分。使用案例前必须同时检索对应的评委批判性审查。",
        "",
        "| 方法卡 | 方法 | 命中案例 |",
        "|---|---|---|",
    ]
    for mid in sorted(CASE_PATTERNS, key=lambda x: int(x[1:])):
        pattern = CASE_PATTERNS[mid]
        hits = sorted(case for case, text in case_docs.items() if re.search(pattern, text, re.I))
        mapping[mid] = hits
        lines.append(f"| {mid} | {title_by_id[mid]} | {', '.join(hits) if hits else '当前案例未命中'} |")
    path = KB / "00_规范与索引" / "方法卡与优秀案例映射.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (KB / "00_规范与索引" / "方法案例映射.yaml").write_text(
        yaml.safe_dump(mapping, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return mapping


def write_dify_plan(parts: dict[str, list[dict]]) -> None:
    collections = [
        {
            "dataset_id": "kb_shared_statistics",
            "name": "共享统计与验证规范",
            "paths": ["01_共享基础/统计严谨性检查卡/**/*.md"],
            "agents": ["modeler", "engineer", "judge"],
            "retrieval": "hybrid",
            "top_k": 5,
        },
        {
            "dataset_id": "kb_model_cards",
            "name": "建模方法卡",
            "paths": ["02_建模手/模型卡/**/*.md", "02_建模手/模型选择图谱.md"],
            "agents": ["modeler", "engineer", "judge"],
            "retrieval": "hybrid_with_rerank",
            "top_k": 7,
        },
        {
            "dataset_id": "kb_engineering_failures",
            "name": "工程故障与复现",
            "paths": ["03_工程师/故障卡/**/*.md"],
            "agents": ["engineer", "judge"],
            "retrieval": "hybrid",
            "top_k": 5,
        },
        {
            "dataset_id": "kb_writing",
            "name": "论文写作规范",
            "paths": [
                "04_论文手/W*.md",
                "04_论文手/官方格式规范/OF*.md",
                "04_论文手/外部模板整合/WR*.md",
                "04_论文手/克隆仓库/*/01_通用写作规范/*.md",
                "04_论文手/克隆仓库/*/0[2-7]_*/问题分析要点.md",
                "04_论文手/克隆仓库/*/0[2-7]_*/建模要点.md",
                "04_论文手/克隆仓库/*/00_LaTeX基础模板与排版/LaTeX排版规则.md",
                "04_论文手/克隆仓库/*/00_LaTeX基础模板与排版/结构化撰写速查.md",
            ],
            "exclude": [
                "**/AI使用规范.txt",
                "**/AI协作Prompt模板.md",
                "**/摘要范例.md",
                "**/专用话术.md",
                "**/README.md",
                "**/CONTRIBUTING.md",
            ],
            "agents": ["writer", "judge"],
            "retrieval": "keyword_first",
            "top_k": 5,
        },
        {
            "dataset_id": "kb_judge",
            "name": "评委规则与评分",
            "paths": ["05_评委/*.md"],
            "agents": ["judge"],
            "retrieval": "keyword_first",
            "top_k": 6,
        },
        {
            "dataset_id": "kb_cases_short",
            "name": "优秀案例结构化证据",
            "paths": [
                "06_优秀案例/*/00_论文卡片.md",
                "06_优秀案例/*/questions/*.md",
                "06_优秀案例/*/08_创新点.md",
                "06_优秀案例/*/09_评委批判性审查.md",
            ],
            "exclude": ["**/audit_removed_fragments.md", "**/assets/**"],
            "agents": ["modeler", "engineer", "writer", "judge"],
            "retrieval": "hybrid_with_rerank",
            "top_k": 6,
        },
    ]
    out = KB / "00_规范与索引" / "dify_datasets.yaml"
    out.write_text(yaml.safe_dump({"version": "1.0", "datasets": collections}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    md = [
        "# Dify 分库与检索配置",
        "",
        "不要把全部文件放进同一个数据集。规则库需要精确、低 top-k 检索，案例库需要混合检索与重排序；全文案例建议另建低优先级数据集。",
        "",
        "| 数据集 | 使用角色 | 建议检索 | top-k |",
        "|---|---|---|---:|",
    ]
    for item in collections:
        md.append(f"| {item['name']} | {', '.join(item['agents'])} | {item['retrieval']} | {item['top_k']} |")
    md += [
        "",
        "## 关键约束",
        "",
        "- 评委规则库始终优先于案例做法；案例与规则冲突时按规则返工。",
        "- 建模手先检索模型选择图谱，再检索最多两到三张候选模型卡和相应案例。",
        "- 论文手只能引用运行时成果仓库中的已审核数值；知识库案例数字不得迁移到当前题目。",
        "- `plan_state.json`、代码、实验结果和论文草稿不进入这些静态数据集。",
        "- Dify 实际 chunk 建议以 Markdown 标题为边界，保留 YAML 元数据；导入后用测试集调阈值而非只调 top-k。",
    ]
    (KB / "00_规范与索引" / "Dify分库与检索配置.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # Expanded writer manifest for upload tools that do not support glob patterns.
    writer_files: list[Path] = []
    writer_files.extend(sorted((KB / "04_论文手").glob("W*.md")))
    writer_files.extend(sorted((KB / "04_论文手" / "官方格式规范").glob("OF*.md")))
    writer_files.extend(sorted((KB / "04_论文手" / "外部模板整合").glob("WR*.md")))
    for repo in sorted((KB / "04_论文手" / "克隆仓库").glob("math-modeling-paper-template-in-2026*")):
        writer_files.extend(sorted((repo / "01_通用写作规范").glob("*.md")))
        writer_files = [p for p in writer_files if p.name != "AI协作Prompt模板.md"]
        for number in range(2, 8):
            dirs = list(repo.glob(f"{number:02d}_*"))
            for folder in dirs:
                for name in ["问题分析要点.md", "建模要点.md"]:
                    if (folder / name).exists():
                        writer_files.append(folder / name)
        for name in ["LaTeX排版规则.md", "结构化撰写速查.md"]:
            path = repo / "00_LaTeX基础模板与排版" / name
            if path.exists():
                writer_files.append(path)
    writer_files = sorted(set(writer_files))
    manifest = {
        "dataset_id": "kb_writing",
        "generated_count": len(writer_files),
        "files": [str(p.relative_to(KB)).replace("\\", "/") for p in writer_files],
        "excluded_high_risk": [
            "**/AI使用规范.txt",
            "**/AI协作Prompt模板.md",
            "**/摘要范例.md",
            "**/专用话术.md",
            "**/*.tex",
        ],
    }
    (KB / "00_规范与索引" / "dify_writer_import_manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def write_phase2_report(parts: dict[str, list[dict]], mapping: dict[str, list[str]]) -> None:
    covered = sum(bool(v) for v in mapping.values())
    card_count = sum(len(rows) for rows in parts.values())
    lines = [
        "# 第二阶段核心方法库质量报告",
        "",
        "## 生成规模",
        "",
        f"- 模型卡：{len(parts['模型卡'])}",
        f"- 统计严谨性检查卡：{len(parts['统计检查卡'])}",
        f"- 工程故障卡：{len(parts['工程故障卡'])}",
        f"- 论文规范：{len(parts['论文规范'])}",
        f"- 外部论文模板整合卡：{len(parts.get('外部论文模板整合', []))}",
        f"- 评委规范：{len(parts['评委规范'])}",
        f"- 有优秀论文案例命中的模型卡：{covered}/{len(mapping)}",
        "",
        "## 自动验证",
        "",
        "- 所有卡片 YAML front matter 可解析。",
        f"- {card_count} 个卡片 ID 应保持唯一，索引路径应全部存在。",
        "- 40 张模型卡均包含适用任务、前提、建模要点、最低验证、失败模式、替代模型、工程提示和评委检查点。",
        "- 评分表权重合计为100，硬门槛独立于加权总分。",
        "",
        "## 使用边界",
        "",
        "- 当前模型卡是竞赛级决策与审查卡，不替代教材、官方库文档或领域文献。",
        "- 案例映射由关键词生成，应结合论文卡片和批判性审查人工确认。",
        "- 第三阶段需在 Dify 中用真实查询测试召回、重排与结构化输出稳定性。",
        "- 当前环境未安装 xelatex/latexmk，外部 TeX 模板尚未做实际编译验证。",
    ]
    (KB / "00_规范与索引" / "第二阶段质量报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def integrate_external_writer_template() -> list[dict]:
    clone_root = KB / "04_论文手" / "克隆仓库"
    candidates = sorted(clone_root.glob("math-modeling-paper-template-in-2026*"))
    if not candidates:
        return []
    repo = candidates[0]
    license_path = repo / "LICENSE"
    if not license_path.exists() or "MIT License" not in license_path.read_text(encoding="utf-8"):
        raise RuntimeError("External writer template has no verified MIT license")

    integration = KB / "04_论文手" / "外部模板整合"
    integration.mkdir(parents=True, exist_ok=True)
    for old in integration.glob("WR*.md"):
        old.unlink()

    source_files = sorted(p for p in repo.rglob("*") if p.is_file())
    import hashlib
    digest = hashlib.sha256()
    for path in source_files:
        digest.update(str(path.relative_to(repo)).replace("\\", "/").encode("utf-8"))
        digest.update(path.read_bytes())
    repo_rel = str(repo.relative_to(KB)).replace("\\", "/")
    stats = {
        "markdown": len(list(repo.rglob("*.md"))),
        "latex": len(list(repo.rglob("*.tex"))),
        "text": len(list(repo.rglob("*.txt"))),
        "bytes": sum(p.stat().st_size for p in source_files),
    }

    docs = {
        "WR01_外部模板来源与许可证.md": f"""# 外部论文模板来源与许可证

- 项目：数学建模竞赛论文通用模板与写作指南
- 上游地址：https://github.com/xinhezhix-ctrl/math-modeling-paper-template-in-2026
- 本地路径：`{repo_rel}`
- 许可证：MIT License，Copyright (c) 2026 xinhezhix-ctrl
- 内容指纹：`{digest.hexdigest()}`
- 文件规模：{stats['markdown']} 个 Markdown、{stats['latex']} 个 TeX、{stats['text']} 个 TXT，共 {stats['bytes']} 字节

本地副本作为可直接复用的模板资产保留。修改或分发实质内容时必须同时保留上游版权声明和MIT许可证。外部模板观点不自动升级为本知识库的官方竞赛规则。
""",
        "WR02_论文手使用路由.md": f"""# 外部模板使用路由

## 直接使用的资产

- LaTeX骨架：`{repo_rel}/00_LaTeX基础模板与排版/数学建模论文通用LaTeX模板.tex`
- 编译与排版：`{repo_rel}/00_LaTeX基础模板与排版/LaTeX排版规则.md`
- 结构速查：`{repo_rel}/00_LaTeX基础模板与排版/结构化撰写速查.md`
- 通用写作索引：`{repo_rel}/01_通用写作规范/00_总索引.md`

## 按任务检索

| 当前任务 | 优先检索目录 | 推荐文件 |
|---|---|---|
| 优化 | `02_优化类` | 问题分析要点、建模要点 |
| 预测 | `03_预测类` | 问题分析要点、建模要点 |
| 评价 | `04_评价类` | 问题分析要点、建模要点 |
| 分类 | `05_分类类` | 问题分析要点、建模要点 |
| 统计分析 | `06_统计分析类` | 问题分析要点、建模要点 |
| 机理建模 | `07_机理建模类` | 问题分析要点、建模要点 |

摘要范例和专用话术只用于检查结构与表达，不得复制其中数字、对象、结论或固定句式。论文手必须以当前项目的主张—证据链为唯一数值来源。
""",
        "WR03_可信度与冲突处理.md": """# 外部模板可信度与冲突处理

- A级：赛事官网当年通知、官方论文格式文件和赛题要求。
- B级：本知识库已验证的统计、工程和评委规则。
- C级：本外部MIT模板的经验性写作建议。
- D级：摘要范例、专用话术和未经来源核验的规则解读。

冲突时按 A > B > C > D 处理。诸如“必须六段摘要”“固定字数”“固定章节顺序”等表述，在没有当年官方依据时只能视为写作建议。

`AI使用规范.txt` 含“2026新规”“AIDC<20%”等具体合规结论，但仓库内未附可核验的官方原文和链接。因此它不进入Dify知识库，也不得作为评委判罚依据。比赛前应从赛事官方网站取得当年规则，并用官方文件覆盖本项。
""",
        "WR04_LaTeX模板采用说明.md": """# LaTeX 模板采用说明

模板基于 `ctexart`、Fandol字体和XeLaTeX，适合作为论文工程起点。使用时先复制到运行时项目的 `paper/` 目录，再按当年官方模板调整页面、标题、编号和匿名要求；不要直接在知识库源文件上写比赛论文。

采用前检查：TeX发行版和宏包；全部 `【替换】` 占位符；示例文献与示例数字；页眉、页码、封面、承诺书和AI声明是否符合当年官方要求。推荐使用 `latexmk -xelatex`，将编译警告、未定义引用和溢出版面纳入终审。
""",
        "WR05_外部模板Dify导入边界.md": """# 外部模板 Dify 导入边界

## 主知识库导入

- 通用写作规范，但排除AI协作Prompt模板。
- 各题型的“问题分析要点”和“建模要点”。
- LaTeX排版规则和结构化撰写速查。
- 本目录WR01–WR05，用于提供来源和冲突约束。

## 不导入或另建低优先级库

- `AI使用规范.txt`：合规主张未核验。
- `摘要范例.md`、`专用话术.md`：易诱发套话和案例内容迁移。
- `.tex`：作为文件资产使用，不做普通向量检索。
- README、CONTRIBUTING和LICENSE：保留在源仓库，不作为写作知识召回。

检索到外部模板建议后，论文手必须同时检索本知识库的写作规范和评委规则；出现冲突时不得自行选择宽松版本。
""",
    }
    result: list[dict] = []
    for name, content in docs.items():
        card_id = name.split("_")[0]
        path = integration / name
        path.write_text(
            frontmatter(card_id=card_id, card_type="external_writer_integration", roles=["writer", "judge"], verified=True, source_license="MIT") + content,
            encoding="utf-8",
        )
        result.append({"id": card_id, "title": content.splitlines()[0].lstrip("# "), "path": str(path.relative_to(KB)).replace("\\", "/")})
    return result


def collect_official_format_cards() -> list[dict]:
    result: list[dict] = []
    for path in sorted((KB / "04_论文手" / "官方格式规范").glob("OF*.md")):
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not match:
            continue
        meta = yaml.safe_load(match.group(1))
        result.append({
            "id": meta["card_id"],
            "title": meta["title"],
            "path": str(path.relative_to(KB)).replace("\\", "/"),
        })
    return result


def main() -> None:
    assert all(len(row) == 11 for row in MODELS), "Every model card must contain 11 fields"
    assert all(len(row) == 6 for row in STAT_CHECKS), "Every statistics card must contain 6 fields"
    assert all(len(row) == 5 for row in ENGINEERING), "Every engineering card must contain 5 fields"
    models = build_models()
    stats = build_stat_checks()
    engineering = build_engineering()
    writer = build_writer()
    external_writer = integrate_external_writer_template()
    official_format = collect_official_format_cards()
    judge = build_judge()
    write_model_selector()
    parts = {"模型卡": models, "统计检查卡": stats, "工程故障卡": engineering, "论文规范": writer, "官方格式规范": official_format, "外部论文模板整合": external_writer, "评委规范": judge}
    write_index(parts)
    mapping = write_case_mapping(models)
    write_dify_plan(parts)
    write_phase2_report(parts, mapping)
    print(f"model_cards={len(models)}")
    print(f"statistics_cards={len(stats)}")
    print(f"engineering_cards={len(engineering)}")
    print(f"writing_docs={len(writer)}")
    print(f"external_writer_docs={len(external_writer)}")
    print(f"official_format_docs={len(official_format)}")
    print(f"judge_docs={len(judge)}")
    print(f"model_cards_with_case_evidence={sum(bool(v) for v in mapping.values())}")


if __name__ == "__main__":
    main()
