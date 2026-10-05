/* ---------- Career Guide tutor system ----------
 * Shared by every role page (dashboard/guide/roles/*.html). Two animated
 * tutor characters (Max / Nova), 10-language narration/subtitles with
 * hard-enforced voice matching, and an "Ask a question" box answered two
 * ways, both offline (no external API call, no account/key of any kind):
 *   1. Name one of the 116 real companies this site tracks (a ticker like
 *      "NVDA" or a company name) and the tutor answers from the Market
 *      Scanner's own data.json -- real price/market-cap/metric/rating,
 *      refreshed daily by this project's own WebSearch-grounded routine
 *      and committed to the repo. Not a per-question internet fetch (this
 *      is a static site with no backend to do that from) and not invented
 *      -- just real, already-gathered data, looked up instead of guessed.
 *   2. Anything else is matched against that role's own built-in
 *      expertise (careers.json's dayToDay/pay/skills content plus a
 *      deeper expertiseQA knowledge base -- comp by level, lifestyle/
 *      hours, core technical mechanics like how an LBO or a DCF works).
 *
 * The narration-language selector is rendered once, on the Guide landing
 * page (index.html) -- every page here reads the same localStorage key,
 * so a language saved on the landing page applies on every role/security
 * page without re-selecting it.
 */

// AI-generated translations of a condensed, two-sentence narration per
// role (what the role does with the market + how it's paid), NOT
// professionally localized -- offered as a best-effort so the mentor
// narration and subtitles aren't English-only, not a guarantee of
// publication-quality translation in every language.
const ROLE_NARRATION = {
  "individual": {
    en: "I manage my own money for goals like retirement, investing directly through a brokerage account and rebalancing only occasionally. I'm not paid by anyone -- I'm the client -- so my only costs are brokerage fees and fund expenses.",
    es: "Gestiono mi propio dinero para metas como la jubilación, invirtiendo directamente a través de una cuenta de corretaje y reequilibrando solo de vez en cuando. Nadie me paga a mí -- yo soy el cliente -- así que mis únicos costos son las comisiones de corretaje y los gastos de los fondos.",
    zh: "我管理自己的钱来实现退休等目标，直接通过经纪账户投资，只是偶尔调整一下资产配置。没有人付钱给我——我就是客户——所以我唯一的成本是经纪费和基金费用。",
    hi: "मैं रिटायरमेंट जैसे लक्ष्यों के लिए अपना पैसा खुद संभालता हूं, एक ब्रोकरेज खाते के ज़रिए सीधे निवेश करता हूं और केवल कभी-कभार पोर्टफोलियो को संतुलित करता हूं। मुझे कोई भुगतान नहीं करता -- मैं ही ग्राहक हूं -- इसलिए मेरी एकमात्र लागत ब्रोकरेज शुल्क और फंड के खर्च हैं।",
    ar: "أدير أموالي الخاصة لتحقيق أهداف مثل التقاعد، فأستثمر مباشرة عبر حساب وساطة وأعيد التوازن أحياناً فقط. لا أحد يدفع لي -- أنا العميل -- لذا فإن تكاليفي الوحيدة هي رسوم الوساطة ومصاريف الصناديق.",
    fr: "Je gère mon propre argent pour des objectifs comme la retraite, en investissant directement via un compte de courtage et en rééquilibrant seulement de temps en temps. Personne ne me paie -- je suis le client -- donc mes seuls coûts sont les frais de courtage et les frais de fonds.",
    pt: "Administro meu próprio dinheiro para objetivos como a aposentadoria, investindo diretamente por uma conta de corretagem e reequilibrando apenas de vez em quando. Ninguém me paga -- eu sou o cliente -- então meus únicos custos são as taxas de corretagem e as despesas dos fundos.",
    ru: "Я управляю своими деньгами ради таких целей, как пенсия, инвестируя напрямую через брокерский счёт и лишь изредка пересматривая портфель. Мне никто не платит -- я клиент -- поэтому мои единственные расходы это брокерские комиссии и расходы фондов.",
    ja: "私は退職などの目標のために自分のお金を自分で管理し、証券口座を通じて直接投資し、たまにしかリバランスしません。誰も私に報酬を払いません――私自身が顧客だからです――だから私の唯一のコストは証券会社の手数料とファンドの費用です。",
    de: "Ich verwalte mein eigenes Geld für Ziele wie den Ruhestand, indem ich direkt über ein Depot investiere und nur gelegentlich umschichte. Niemand bezahlt mich -- ich bin der Kunde -- also sind meine einzigen Kosten Handelsgebühren und Fondskosten.",
  },
  "advisor": {
    en: "I build investment plans for other people, turning a client's goals like retirement or college savings into a target return and risk level. I'm usually paid a percentage of the assets I manage for my clients, typically around one percent a year.",
    es: "Elaboro planes de inversión para otras personas, convirtiendo sus metas en un rendimiento objetivo y un nivel de riesgo, y paso mis días en reuniones con clientes y ayudándolos a sobrellevar las caídas del mercado. Normalmente me pagan un porcentaje de los activos que gestiono, alrededor del uno por ciento al año.",
    zh: "我为其他人制定投资计划，把他们的目标转化为目标收益率和风险水平，每天大部分时间都在与客户会面，并在市场下跌时帮助他们保持冷静。通常我收取所管理资产的一定比例作为报酬，大约每年百分之一。",
    hi: "मैं दूसरे लोगों के लिए निवेश योजनाएं बनाता हूं, उनके लक्ष्यों को एक निश्चित रिटर्न और जोखिम स्तर में बदलता हूं, और मेरा ज़्यादातर समय ग्राहकों से मिलने और बाज़ार गिरने पर उन्हें शांत रखने में जाता है। आमतौर पर मुझे प्रबंधित संपत्ति का एक प्रतिशत भुगतान मिलता है, लगभग एक प्रतिशत सालाना।",
    ar: "أضع خطط استثمار لأشخاص آخرين، محولاً أهدافهم إلى عائد مستهدف ومستوى مخاطرة، وأقضي أيامي في اجتماعات مع العملاء ومساعدتهم على تجاوز تراجعات السوق دون ذعر. عادة ما أتقاضى نسبة مئوية من الأصول التي أديرها، حوالي واحد بالمئة سنوياً.",
    fr: "Je construis des plans d'investissement pour d'autres personnes, en transformant leurs objectifs en un rendement cible et un niveau de risque, et je passe mes journées en rendez-vous clients et à les accompagner pendant les baisses de marché. Je suis généralement payé un pourcentage des actifs que je gère, environ un pour cent par an.",
    pt: "Crio planos de investimento para outras pessoas, transformando seus objetivos em um retorno-alvo e um nível de risco, e passo meus dias em reuniões com clientes e ajudando-os a enfrentar quedas do mercado. Geralmente sou pago uma porcentagem dos ativos que administro, cerca de um por cento ao ano.",
    ru: "Я составляю инвестиционные планы для других людей, превращая их цели в целевую доходность и уровень риска, и провожу дни на встречах с клиентами, помогая им не паниковать во время падений рынка. Обычно мне платят процент от активов, которыми я управляю, около одного процента в год.",
    ja: "私は他の人のために投資プランを作り、その人の目標を目標リターンとリスク水準に変え、クライアントとの面談や、相場下落時にパニックにならないよう支える仕事に日々を費やしています。報酬は通常、運用資産の一定割合で、年に約1パーセントほどです。",
    de: "Ich erstelle Anlagepläne für andere Menschen, indem ich ihre Ziele in eine Zielrendite und ein Risikoniveau übersetze, und verbringe meine Tage mit Kundengesprächen und dem Beistand bei Marktrückgängen. Ich werde normalerweise mit einem Prozentsatz des verwalteten Vermögens bezahlt, etwa ein Prozent pro Jahr.",
  },
  "private-banker": {
    en: "I manage a whole book of wealthy clients at once, each with their own goals and often a large concentrated stock position needing careful handling. I'm paid a salary plus a percentage of the assets my clients keep with the bank.",
    es: "Gestiono toda una cartera de clientes adinerados a la vez, cada uno con sus propias metas y a menudo una gran posición concentrada en acciones que requiere un manejo cuidadoso. Me pagan un salario más un porcentaje de los activos que mis clientes mantienen en el banco.",
    zh: "我同时管理一整批富裕客户，每个人都有自己的目标，通常还持有需要谨慎处理的大额集中股票仓位。我的收入是薪水加上客户在银行保留资产的一定比例。",
    hi: "मैं एक साथ कई धनी ग्राहकों को संभालता हूं, जिनमें से हर एक के अपने लक्ष्य होते हैं और अक्सर एक बड़ा संकेंद्रित शेयर निवेश होता है जिसे सावधानी से संभालना पड़ता है। मुझे वेतन के साथ-साथ मेरे ग्राहकों द्वारा बैंक में रखी गई संपत्ति का एक प्रतिशत मिलता है।",
    ar: "أدير دفتر عملاء أثرياء بأكمله في آن واحد، لكل منهم أهدافه الخاصة وغالباً مركز كبير مركّز في الأسهم يحتاج إلى عناية خاصة. أتقاضى راتباً بالإضافة إلى نسبة من الأصول التي يحتفظ بها عملائي لدى البنك.",
    fr: "Je gère tout un portefeuille de clients fortunés à la fois, chacun avec ses propres objectifs et souvent une position importante concentrée en actions nécessitant une attention particulière. Je suis payé un salaire plus un pourcentage des actifs que mes clients conservent à la banque.",
    pt: "Administro toda uma carteira de clientes ricos ao mesmo tempo, cada um com seus próprios objetivos e muitas vezes uma grande posição concentrada em ações que exige cuidado especial. Sou pago um salário mais uma porcentagem dos ativos que meus clientes mantêm no banco.",
    ru: "Я одновременно веду целую книгу состоятельных клиентов, у каждого свои цели и часто крупная концентрированная позиция в акциях, требующая осторожного обращения. Мне платят зарплату плюс процент от активов, которые мои клиенты держат в банке.",
    ja: "私は裕福な顧客を一度に何人もまとめて担当し、それぞれが独自の目標を持ち、しばしば慎重な対応が必要な大きな集中株式ポジションを抱えています。報酬は給与に加えて、顧客が銀行に預けている資産の一定割合です。",
    de: "Ich betreue gleichzeitig ein ganzes Buch wohlhabender Kunden, jeder mit eigenen Zielen und oft einer großen konzentrierten Aktienposition, die sorgfältige Betreuung braucht. Ich werde mit einem Gehalt plus einem Prozentsatz des Vermögens bezahlt, das meine Kunden bei der Bank halten.",
  },
  "investment-banker": {
    en: "I advise companies on raising money and doing deals, like taking a company public or merging with another, building financial models and pitch books. I'm paid a salary plus a large bonus tied to how many deals my team closes.",
    es: "Asesoro a empresas en la obtención de capital y en operaciones, como sacar una empresa a bolsa o fusionarla con otra, elaborando modelos financieros y presentaciones. Me pagan un salario más una gran bonificación ligada a cuántas operaciones cierra mi equipo.",
    zh: "我为企业提供融资和并购交易方面的建议，比如帮助公司上市或与另一家公司合并，并制作财务模型和推介材料。我的收入是薪水加上与团队完成交易数量挂钩的高额奖金。",
    hi: "मैं कंपनियों को पूंजी जुटाने और सौदों, जैसे किसी कंपनी को शेयर बाज़ार में लाना या किसी और कंपनी के साथ विलय करना, में सलाह देता हूं और वित्तीय मॉडल व प्रेजेंटेशन बनाता हूं। मुझे वेतन के साथ एक बड़ा बोनस मिलता है जो मेरी टीम द्वारा पूरे किए गए सौदों की संख्या से जुड़ा होता है।",
    ar: "أقدم استشارات للشركات حول جمع الأموال وإتمام الصفقات، مثل طرح شركة للاكتتاب العام أو دمجها مع شركة أخرى، وأبني نماذج مالية وعروضاً تقديمية. أتقاضى راتباً بالإضافة إلى مكافأة كبيرة مرتبطة بعدد الصفقات التي يبرمها فريقي.",
    fr: "Je conseille les entreprises sur la levée de fonds et les opérations, comme l'introduction en bourse ou la fusion avec une autre société, en construisant des modèles financiers et des présentations. Je suis payé un salaire plus une grosse prime liée au nombre d'opérations conclues par mon équipe.",
    pt: "Assessoro empresas na captação de recursos e em negócios, como abrir capital na bolsa ou se fundir com outra empresa, construindo modelos financeiros e apresentações. Sou pago um salário mais um grande bônus ligado a quantos negócios minha equipe fecha.",
    ru: "Я консультирую компании по привлечению капитала и сделкам, например по выходу на биржу или слиянию с другой компанией, строя финансовые модели и презентации. Мне платят зарплату плюс крупный бонус, привязанный к числу сделок, которые закрывает моя команда.",
    ja: "私は企業の資金調達や、上場や他社との合併といった取引について助言し、財務モデルや提案資料を作成します。報酬は給与に加えて、チームがまとめた取引の数に連動する大きなボーナスです。",
    de: "Ich berate Unternehmen bei der Kapitalbeschaffung und bei Transaktionen, etwa einem Börsengang oder einer Fusion, und erstelle dabei Finanzmodelle und Präsentationen. Ich werde mit einem Gehalt plus einem großen Bonus bezahlt, der an die Anzahl der Abschlüsse meines Teams gekoppelt ist.",
  },
  "trader": {
    en: "I buy and sell constantly -- executing client trades, risking a firm's money, or trading my own account -- over minutes or hours, not years. I'm paid a share of the profits I generate, which can mean a small base salary but big upside.",
    es: "Compro y vendo constantemente -- ejecutando operaciones de clientes, arriesgando el dinero de la firma o operando mi propia cuenta -- en cuestión de minutos u horas, no años. Me pagan una parte de las ganancias que genero, lo que puede significar un salario base pequeño pero un gran potencial.",
    zh: "我不断地买入卖出——执行客户的交易、动用公司自己的资金，或者交易自己的账户——时间以分钟或小时计算，而不是年。我的收入是我所创造利润的一部分，这可能意味着基本工资很低，但潜在收益很大。",
    hi: "मैं लगातार खरीदता और बेचता हूं -- ग्राहकों के ऑर्डर पूरे करके, फर्म का पैसा जोखिम में डालकर, या अपने खाते से व्यापार करके -- मिनटों या घंटों में, सालों में नहीं। मुझे अपने द्वारा कमाए गए मुनाफे का एक हिस्सा मिलता है, जिसका मतलब छोटा बेस वेतन लेकिन बड़ी संभावना हो सकता है।",
    ar: "أشتري وأبيع باستمرار -- أنفذ أوامر العملاء، أو أخاطر بأموال الشركة، أو أتداول بحسابي الخاص -- خلال دقائق أو ساعات، وليس سنوات. أتقاضى حصة من الأرباح التي أحققها، وهو ما قد يعني راتباً أساسياً صغيراً لكن إمكانية كبيرة للربح.",
    fr: "J'achète et je vends constamment -- en exécutant les ordres des clients, en risquant l'argent de la firme, ou en tradant mon propre compte -- en quelques minutes ou quelques heures, pas en années. Je suis payé une part des profits que je génère, ce qui peut signifier un petit salaire de base mais un fort potentiel.",
    pt: "Compro e vendo constantemente -- executando ordens de clientes, arriscando o dinheiro da firma, ou negociando minha própria conta -- em minutos ou horas, não anos. Sou pago uma parte dos lucros que gero, o que pode significar um salário base pequeno, mas um grande potencial.",
    ru: "Я постоянно покупаю и продаю -- исполняю заявки клиентов, рискую деньгами фирмы или торгую на собственном счёте -- в течение минут или часов, а не лет. Мне платят долю от прибыли, которую я приношу, что может означать небольшой оклад, но большой потенциал.",
    ja: "私は絶えず売買しています――顧客の注文を執行したり、会社の資金を運用したり、自分の口座で取引したりと、年単位ではなく分や時間単位です。報酬は自分が生み出した利益の一部で、基本給は小さくても大きな可能性があります。",
    de: "Ich kaufe und verkaufe ständig -- führe Kundenaufträge aus, setze das Geld der Firma ein oder handle mein eigenes Konto -- innerhalb von Minuten oder Stunden, nicht Jahren. Ich werde mit einem Anteil der von mir erzielten Gewinne bezahlt, was ein kleines Grundgehalt, aber großes Potenzial bedeuten kann.",
  },
  "quant": {
    en: "I build statistical models that find patterns in prices and let an algorithm trade on them automatically, testing every idea against historical data first. I'm paid a strong base salary plus a bonus tied to how well my strategies perform.",
    es: "Construyo modelos estadísticos que encuentran patrones en los precios y dejo que un algoritmo opere con ellos automáticamente, probando cada idea primero con datos históricos. Me pagan un salario base sólido más una bonificación ligada al rendimiento de mis estrategias.",
    zh: "我构建统计模型来发现价格中的规律，并让算法自动据此交易，每个想法都先用历史数据测试过。我的收入是一份不错的基本工资，加上与策略表现挂钩的奖金。",
    hi: "मैं सांख्यिकीय मॉडल बनाता हूं जो कीमतों में पैटर्न ढूंढते हैं और एक एल्गोरिदम को उन पर स्वचालित रूप से व्यापार करने देता हूं, हर विचार को पहले ऐतिहासिक आंकड़ों पर परखा जाता है। मुझे एक मज़बूत बेस वेतन के साथ-साथ मेरी रणनीतियों के प्रदर्शन से जुड़ा बोनस मिलता है।",
    ar: "أبني نماذج إحصائية تكتشف أنماطاً في الأسعار وأترك خوارزمية تتداول بناءً عليها تلقائياً، بعد اختبار كل فكرة على بيانات تاريخية أولاً. أتقاضى راتباً أساسياً جيداً بالإضافة إلى مكافأة مرتبطة بأداء استراتيجياتي.",
    fr: "Je construis des modèles statistiques qui repèrent des tendances dans les prix et je laisse un algorithme trader automatiquement, en testant chaque idée d'abord sur des données historiques. Je suis payé un bon salaire de base plus une prime liée à la performance de mes stratégies.",
    pt: "Construo modelos estatísticos que encontram padrões nos preços e deixo um algoritmo negociar com eles automaticamente, testando cada ideia primeiro com dados históricos. Sou pago um salário base sólido mais um bônus ligado ao desempenho das minhas estratégias.",
    ru: "Я строю статистические модели, которые находят закономерности в ценах, и позволяю алгоритму торговать по ним автоматически, сначала проверяя каждую идею на исторических данных. Мне платят солидный оклад плюс бонус, привязанный к результатам моих стратегий.",
    ja: "私は価格の中にあるパターンを見つける統計モデルを構築し、アルゴリズムに自動で取引させます。どのアイデアもまず過去のデータで検証します。報酬はしっかりした基本給に加え、戦略の成績に連動するボーナスです。",
    de: "Ich entwickle statistische Modelle, die Muster in Preisen finden, und lasse einen Algorithmus automatisch danach handeln, nachdem jede Idee zuerst an historischen Daten getestet wurde. Ich werde mit einem soliden Grundgehalt plus einem Bonus bezahlt, der an die Leistung meiner Strategien gekoppelt ist.",
  },
  "private-equity": {
    en: "I help buy whole companies outright, often using borrowed money, then spend years improving how they're run before selling. My real payday comes years later, as a share of the profits when those companies are sold.",
    es: "Ayudo a comprar empresas enteras, a menudo usando dinero prestado, y luego paso años mejorando su gestión antes de venderlas. Mi verdadera recompensa llega años después, como una parte de las ganancias cuando se venden esas empresas.",
    zh: "我帮助整体收购公司，通常使用借来的资金，然后花几年时间改善公司的经营，再将其出售。我真正的回报要在多年后才出现，是这些公司出售时利润中的一部分。",
    hi: "मैं पूरी कंपनियों को खरीदने में मदद करता हूं, अक्सर उधार के पैसे से, और फिर उन्हें बेचने से पहले सालों तक उनके संचालन को बेहतर बनाता हूं। मेरा असली फायदा सालों बाद, इन कंपनियों के बिकने पर मुनाफे के हिस्से के रूप में मिलता है।",
    ar: "أساعد في شراء شركات بأكملها، غالباً باستخدام أموال مقترضة، ثم أقضي سنوات في تحسين إدارتها قبل بيعها. مكسبي الحقيقي يأتي بعد سنوات، كحصة من الأرباح عند بيع تلك الشركات.",
    fr: "J'aide à racheter des entreprises entières, souvent avec de l'argent emprunté, puis je passe des années à améliorer leur gestion avant de les revendre. Mon vrai gain arrive des années plus tard, sous forme de part des profits lors de la revente de ces entreprises.",
    pt: "Ajudo a comprar empresas inteiras, muitas vezes usando dinheiro emprestado, e depois passo anos melhorando sua gestão antes de vendê-las. Meu verdadeiro ganho vem anos depois, como uma parte dos lucros quando essas empresas são vendidas.",
    ru: "Я помогаю полностью выкупать компании, часто на заёмные деньги, а затем годами улучшаю управление ими перед продажей. Моя настоящая награда приходит годы спустя, в виде доли прибыли при продаже этих компаний.",
    ja: "私は企業を丸ごと買収する手助けをし、多くの場合借入金を使い、売却するまでの数年間、経営を改善することに時間を費やします。本当の報酬は何年も後、企業が売却される際の利益の分配として得られます。",
    de: "Ich helfe dabei, ganze Unternehmen aufzukaufen, oft mit geliehenem Geld, und verbringe dann Jahre damit, ihre Führung zu verbessern, bevor sie verkauft werden. Mein eigentlicher Gewinn kommt Jahre später, als Anteil am Gewinn, wenn diese Unternehmen verkauft werden.",
  },
  "venture-capital": {
    en: "I fund young private companies years before they could trade publicly, betting a few big winners will make up for the many that fail. I earn a management fee on the money I oversee, plus a share of the profits if my bets pay off.",
    es: "Financio empresas privadas jóvenes años antes de que puedan cotizar en bolsa, apostando a que unos pocos grandes éxitos compensen a las muchas que fracasan. Gano una comisión de gestión sobre el dinero que superviso, más una parte de las ganancias si mis apuestas resultan bien.",
    zh: "我在年轻的私人公司能够公开交易的许多年之前就为它们提供资金，赌的是少数几个大赢家能够弥补众多失败者的损失。我从所管理的资金中收取管理费，如果投资成功，还能获得一部分利润。",
    hi: "मैं युवा निजी कंपनियों को उनके सार्वजनिक रूप से व्यापार कर पाने से सालों पहले फंड देता हूं, यह दांव लगाते हुए कि कुछ बड़ी सफलताएं कई असफलताओं की भरपाई कर देंगी। मुझे जिस पैसे की देखरेख करता हूं उस पर एक प्रबंधन शुल्क मिलता है, और अगर मेरे दांव सही निकलते हैं तो मुनाफे का एक हिस्सा भी।",
    ar: "أموّل شركات ناشئة خاصة قبل سنوات من إمكانية تداولها علناً، مراهناً على أن بضعة نجاحات كبيرة ستعوض الإخفاقات الكثيرة. أكسب رسم إدارة على الأموال التي أشرف عليها، بالإضافة إلى حصة من الأرباح إذا نجحت رهاناتي.",
    fr: "Je finance de jeunes entreprises privées des années avant qu'elles ne puissent entrer en bourse, en pariant que quelques grands succès compenseront les nombreux échecs. Je gagne des frais de gestion sur l'argent que je supervise, plus une part des profits si mes paris sont gagnants.",
    pt: "Financio empresas privadas jovens anos antes de poderem negociar publicamente, apostando que alguns grandes sucessos vão compensar as muitas que falham. Ganho uma taxa de administração sobre o dinheiro que superviso, além de uma parte dos lucros se minhas apostas derem certo.",
    ru: "Я финансирую молодые частные компании за годы до того, как они смогли бы торговаться на бирже, делая ставку на то, что несколько крупных успехов окупят множество неудач. Я зарабатываю на комиссии за управление деньгами, которыми я распоряжаюсь, плюс долю прибыли, если мои ставки оправдываются.",
    ja: "私は若い非公開企業に、公開市場で取引される何年も前から資金を提供し、数少ない大成功が多くの失敗を補うことに賭けています。管理している資金に対する運用手数料を得て、賭けがうまくいけば利益の一部も得られます。",
    de: "Ich finanziere junge private Unternehmen Jahre bevor sie überhaupt an der Börse gehandelt werden könnten, in der Hoffnung, dass einige wenige große Erfolge die vielen Fehlschläge ausgleichen. Ich verdiene eine Verwaltungsgebühr auf das von mir betreute Geld, plus einen Gewinnanteil, wenn meine Wetten aufgehen.",
  },
  "hedge-fund": {
    en: "I manage pooled money from investors, trying to make money whether markets go up or down, often betting stocks will fall as well as rise. I'm typically paid a management fee plus a meaningful share of the profits I generate.",
    es: "Gestiono dinero conjunto de inversores, tratando de ganar dinero tanto si el mercado sube como si baja, a menudo apostando a que las acciones caerán tanto como a que subirán. Normalmente me pagan una comisión de gestión más una parte considerable de las ganancias que genero.",
    zh: "我管理来自投资者的集合资金，设法无论市场上涨还是下跌都能赚钱，常常既押注股票下跌也押注股票上涨。我通常收取管理费，再加上我所创造利润中相当可观的一部分。",
    hi: "मैं निवेशकों के साझा पैसे का प्रबंधन करता हूं, यह कोशिश करते हुए कि बाज़ार ऊपर जाए या नीचे, दोनों ही हालात में पैसा कमाया जा सके, अक्सर शेयरों के गिरने और चढ़ने दोनों पर दांव लगाकर। आमतौर पर मुझे एक प्रबंधन शुल्क के साथ-साथ मेरे द्वारा कमाए गए मुनाफे का एक बड़ा हिस्सा मिलता है।",
    ar: "أدير أموالاً مجمعة من المستثمرين، محاولاً تحقيق أرباح سواء ارتفع السوق أو انخفض، وغالباً ما أراهن على انخفاض الأسهم بقدر ارتفاعها. عادة ما أتقاضى رسم إدارة بالإضافة إلى حصة كبيرة من الأرباح التي أحققها.",
    fr: "Je gère de l'argent mis en commun par des investisseurs, en essayant de gagner de l'argent que le marché monte ou descende, en pariant souvent que des actions vont baisser autant que monter. Je suis généralement payé des frais de gestion plus une part importante des profits que je génère.",
    pt: "Administro dinheiro reunido de investidores, tentando ganhar dinheiro independentemente de o mercado subir ou cair, muitas vezes apostando que ações vão cair tanto quanto subir. Geralmente sou pago uma taxa de administração mais uma parte significativa dos lucros que gero.",
    ru: "Я управляю объединёнными деньгами инвесторов, пытаясь зарабатывать независимо от того, растёт рынок или падает, часто делая ставку как на падение, так и на рост акций. Обычно мне платят комиссию за управление плюс существенную долю прибыли, которую я приношу.",
    ja: "私は投資家からの資金をまとめて運用し、相場が上がっても下がっても利益を出そうとし、しばしば株が下がることにも上がることにも賭けます。報酬は通常、運用手数料に加え、生み出した利益のかなりの部分です。",
    de: "Ich verwalte gebündeltes Geld von Investoren und versuche, Geld zu verdienen, egal ob der Markt steigt oder fällt, oft indem ich darauf wette, dass Aktien ebenso fallen wie steigen. Ich werde meist mit einer Verwaltungsgebühr plus einem bedeutenden Anteil der von mir erzielten Gewinne bezahlt.",
  },
  "cfo": {
    en: "My own company is the one being bought and sold, so I decide things like whether to buy back stock or raise the dividend, and present results to the board. I'm paid a salary and bonus, plus company stock that ties my wealth to the share price.",
    es: "Mi propia empresa es la que se compra y se vende, así que decido cosas como si recomprar acciones o aumentar el dividendo, y presento los resultados a la junta directiva. Me pagan un salario y una bonificación, más acciones de la empresa que ligan mi propia riqueza al precio de la acción.",
    zh: "我自己的公司正是被买卖的对象，所以由我决定是否回购股票或提高股息之类的事情，并向董事会汇报业绩。我的收入是薪水和奖金，再加上公司股票，这让我自己的财富与股价挂钩。",
    hi: "मेरी अपनी कंपनी ही वह है जिसे खरीदा और बेचा जाता है, इसलिए मैं यह तय करता हूं कि शेयर वापस खरीदे जाएं या डिविडेंड बढ़ाया जाए, और बोर्ड के सामने नतीजे पेश करता हूं। मुझे वेतन और बोनस के साथ-साथ कंपनी के शेयर मिलते हैं, जो मेरी अपनी संपत्ति को शेयर की कीमत से जोड़ देते हैं。",
    ar: "شركتي نفسها هي التي تُشترى وتُباع، لذا أقرر أموراً مثل إعادة شراء الأسهم أو رفع الأرباح الموزعة، وأعرض النتائج على مجلس الإدارة. أتقاضى راتباً ومكافأة، بالإضافة إلى أسهم في الشركة تربط ثروتي الخاصة بسعر السهم.",
    fr: "Ma propre entreprise est celle qu'on achète et qu'on vend, donc je décide des choses comme racheter des actions ou augmenter le dividende, et je présente les résultats au conseil d'administration. Je suis payé un salaire et une prime, plus des actions de l'entreprise qui lient ma propre richesse au cours de l'action.",
    pt: "Minha própria empresa é a que está sendo comprada e vendida, então decido coisas como recomprar ações ou aumentar o dividendo, e apresento resultados ao conselho. Sou pago um salário e bônus, além de ações da empresa que ligam minha própria riqueza ao preço da ação.",
    ru: "Моя собственная компания -- это та, которую покупают и продают, поэтому я решаю такие вопросы, как обратный выкуп акций или увеличение дивидендов, и представляю результаты совету директоров. Мне платят зарплату и бонус, плюс акции компании, которые привязывают моё благосостояние к цене акций.",
    ja: "私自身の会社こそが売買される側なので、自社株買いをするか配当を増やすかといったことを決め、取締役会に業績を報告します。報酬は給与とボーナスに加え、自分の資産を株価に連動させる自社株です。",
    de: "Mein eigenes Unternehmen ist dasjenige, das gekauft und verkauft wird, also entscheide ich Dinge wie Aktienrückkäufe oder Dividendenerhöhungen und präsentiere Ergebnisse dem Vorstand. Ich werde mit Gehalt und Bonus bezahlt, plus Unternehmensaktien, die mein eigenes Vermögen an den Aktienkurs koppeln.",
  },
  "market-maker": {
    en: "I continuously quote a price I'll buy at and a slightly higher price I'll sell at, making money on that small gap across huge volume. I'm paid from the spread I capture, so my income depends on volume and discipline, not predicting the market.",
    es: "Cotizo continuamente un precio al que compro y uno ligeramente más alto al que vendo, ganando dinero con esa pequeña diferencia gracias a un volumen enorme. Me pagan del margen que capturo, así que mis ingresos dependen del volumen y la disciplina, no de predecir el mercado.",
    zh: "我持续报出我愿意买入的价格和略高一些的卖出价格，依靠巨大的交易量从这一小差价中获利，而不是押注股票的涨跌方向。我的收入来自我所赚取的价差，所以我的收入取决于交易量和纪律，而不是预测市场。",
    hi: "मैं लगातार एक कीमत बताता हूं जिस पर मैं खरीदूंगा और उससे थोड़ी ज़्यादा कीमत जिस पर बेचूंगा, और भारी मात्रा में लेन-देन से इस छोटे से अंतर पर कमाई करता हूं। मुझे उस स्प्रेड से भुगतान मिलता है जो मैं हासिल करता हूं, इसलिए मेरी कमाई मात्रा और अनुशासन पर निर्भर करती है, बाज़ार का अनुमान लगाने पर नहीं।",
    ar: "أعرض باستمرار سعراً أشتري به وسعراً أعلى قليلاً أبيع به، فأربح من هذا الفارق الصغير عبر حجم تداول ضخم. أتقاضى أجري من الفارق الذي أحققه، لذا يعتمد دخلي على الحجم والانضباط، لا على توقع اتجاه السوق.",
    fr: "Je cote en continu un prix auquel j'achète et un prix légèrement plus élevé auquel je vends, en gagnant de l'argent sur ce petit écart grâce à un volume énorme. Je suis payé sur l'écart que je capture, donc mes revenus dépendent du volume et de la discipline, pas de prédire le marché.",
    pt: "Cotizo continuamente um preço pelo qual compro e um preço um pouco mais alto pelo qual vendo, ganhando dinheiro com essa pequena diferença em um volume enorme. Sou pago a partir do spread que capturo, então minha renda depende de volume e disciplina, não de prever o mercado.",
    ru: "Я постоянно называю цену, по которой покупаю, и чуть более высокую цену, по которой продаю, зарабатывая на этой небольшой разнице за счёт огромного объёма. Мне платят за спред, который я захватываю, поэтому мой доход зависит от объёма и дисциплины, а не от предсказания рынка.",
    ja: "私は常に買う価格とわずかに高い売る価格を提示し続け、その小さな差額を膨大な取引量で稼ぎます。相場の方向を予測するのではなく、獲得したスプレッドから報酬を得るため、収入は取引量と規律次第です。",
    de: "Ich stelle fortlaufend einen Preis, zu dem ich kaufe, und einen leicht höheren Preis, zu dem ich verkaufe, und verdiene an dieser kleinen Spanne bei riesigem Volumen. Ich werde aus der erfassten Spanne bezahlt, sodass mein Einkommen von Volumen und Disziplin abhängt, nicht davon, den Markt vorherzusagen.",
  },
  "research-analyst": {
    en: "I study public companies in depth and publish an opinion on whether their stock is worth buying, built on detailed financial models. I'm paid a salary and bonus tied to how accurate and influential my research turns out to be.",
    es: "Estudio empresas públicas a fondo y publico una opinión sobre si vale la pena comprar sus acciones, basada en modelos financieros detallados. Me pagan un salario y una bonificación ligados a la precisión e influencia de mi investigación.",
    zh: "我深入研究上市公司，并根据详细的财务模型发表关于其股票是否值得买入的意见。我的薪水和奖金与我研究的准确性和影响力挂钩。",
    hi: "मैं सार्वजनिक कंपनियों का गहराई से अध्ययन करता हूं और विस्तृत वित्तीय मॉडलों के आधार पर यह राय प्रकाशित करता हूं कि उनका शेयर खरीदने लायक है या नहीं। मुझे वेतन और बोनस मिलता है जो मेरे शोध की सटीकता और प्रभाव से जुड़ा होता है।",
    ar: "أدرس الشركات المدرجة بعمق وأنشر رأياً حول ما إذا كان سهمها يستحق الشراء، استناداً إلى نماذج مالية مفصلة. أتقاضى راتباً ومكافأة مرتبطين بدقة أبحاثي ومدى تأثيرها.",
    fr: "J'étudie en profondeur des entreprises cotées et je publie un avis sur si leur action vaut la peine d'être achetée, basé sur des modèles financiers détaillés. Je suis payé un salaire et une prime liés à la précision et à l'influence de mes recherches.",
    pt: "Estudo empresas públicas a fundo e publico uma opinião sobre se vale a pena comprar suas ações, baseada em modelos financeiros detalhados. Sou pago um salário e bônus ligados à precisão e influência da minha pesquisa.",
    ru: "Я глубоко изучаю публичные компании и публикую мнение о том, стоит ли покупать их акции, основанное на подробных финансовых моделях. Мне платят зарплату и бонус, привязанные к точности и влиятельности моих исследований.",
    ja: "私は上場企業を詳しく調べ、詳細な財務モデルに基づいてその株が買う価値があるかどうかの意見を公表します。報酬は給与とボーナスで、自分の分析の正確さと影響力に連動します。",
    de: "Ich untersuche börsennotierte Unternehmen gründlich und veröffentliche eine Einschätzung, ob sich der Kauf ihrer Aktie lohnt, basierend auf detaillierten Finanzmodellen. Ich werde mit Gehalt und Bonus bezahlt, die an die Genauigkeit und den Einfluss meiner Recherche gekoppelt sind.",
  },
  "risk-manager": {
    en: "I don't pick any stocks -- my job is making sure nobody else at the firm takes on so much risk it could sink us, starting each day with risk reports. I'm paid a salary and bonus, usually smaller than the traders and bankers I keep an eye on.",
    es: "No elijo ninguna acción -- mi trabajo es asegurarme de que nadie más en la firma asuma tanto riesgo que pueda hundirnos, empezando cada día con informes de riesgo. Me pagan un salario y una bonificación, normalmente menores que los de los operadores y banqueros a los que superviso.",
    zh: "我完全不挑选股票——我的工作是确保公司里没有人承担过大的风险而可能拖垮公司，每天都从风险报告开始。我的薪水和奖金通常比我监督的交易员和银行家要低。",
    hi: "मैं कोई शेयर नहीं चुनता -- मेरा काम यह सुनिश्चित करना है कि फर्म में कोई और इतना जोखिम न ले कि हमें डुबो दे, और मैं हर दिन की शुरुआत जोखिम रिपोर्टों से करता हूं। मुझे वेतन और बोनस मिलता है, जो आमतौर पर उन ट्रेडरों और बैंकरों से कम होता है जिन पर मैं नज़र रखता हूं।",
    ar: "لا أختار أي أسهم -- مهمتي هي التأكد من ألا يتحمل أحد آخر في الشركة مخاطرة كبيرة قد تغرقنا، وأبدأ كل يوم بتقارير المخاطر. أتقاضى راتباً ومكافأة، عادة أقل مما يتقاضاه المتداولون والمصرفيون الذين أراقبهم.",
    fr: "Je ne choisis aucune action -- mon travail est de m'assurer que personne d'autre dans la firme ne prend assez de risques pour nous couler, en commençant chaque journée par des rapports de risque. Je suis payé un salaire et une prime, généralement inférieurs à ceux des traders et banquiers que je surveille.",
    pt: "Não escolho nenhuma ação -- meu trabalho é garantir que ninguém mais na firma assuma tanto risco a ponto de nos afundar, começando cada dia com relatórios de risco. Sou pago um salário e bônus, geralmente menores que os dos traders e banqueiros que superviso.",
    ru: "Я вообще не выбираю акции -- моя работа следить, чтобы никто другой в фирме не брал на себя столько риска, что это могло бы нас потопить, начиная каждый день с отчётов о рисках. Мне платят зарплату и бонус, обычно меньшие, чем у трейдеров и банкиров, за которыми я слежу.",
    ja: "私は一切株を選びません――私の仕事は、会社の誰かが会社を沈めかねないほどのリスクを取らないようにすることで、毎日リスクレポートから一日を始めます。報酬は給与とボーナスで、通常は私が監視するトレーダーや銀行員より少なめです。",
    de: "Ich wähle keine Aktien aus -- meine Aufgabe ist sicherzustellen, dass niemand sonst in der Firma so viel Risiko eingeht, dass es uns zu Fall bringen könnte, beginnend jeden Tag mit Risikoberichten. Ich werde mit Gehalt und Bonus bezahlt, meist weniger als die Trader und Banker, die ich im Auge behalte.",
  },
};

const LANG_VOICE_DB = {
  "en": { label: "English", native: "English", prefixes: ["en"], female: ["emmamultilingual", "avamultilingual", "jenny", "aria", "michelle", "ana", "sonia", "libby", "maisie", "natasha", "hayley", "clara", "heather", "neerja", "emily", "leah", "yan", "asilia", "molly", "ezinne", "rosa", "luna", "imani", "google us english", "google uk english female", "ava", "zoe", "allison", "nicky", "samantha", "joelle", "kate", "stephanie", "serena", "martha", "matilda", "karen", "catherine", "tara", "isha", "sangeeta", "veena", "moira", "tessa", "fiona", "zira", "hazel", "susan", "linda", "heera", "google us english 5 (natural)", "google us english 1 (natural)", "google us english 2 (natural)", "google us english 7 (natural)", "android speech recognition and synthesis from google en-us-x-sfg-network", "chrome os us english 8", "google uk english 2 (natural)", "google uk english 4 (natural)", "google uk english 6 (natural)", "chrome os uk english 7", "google australian english 1 (natural)", "google australian english 3 (natural)", "android speech recognition and synthesis from google en-in-x-ena-network", "android speech recognition and synthesis from google en-in-x-enc-network"], male: ["andrewmultilingual", "brianmultilingual", "guy", "eric", "steffan", "christopher", "roger", "ryan", "thomas", "william", "liam", "prabhat", "connor", "luke", "sam", "chilemba", "mitchell", "abeo", "james", "wayne", "elimu", "google uk english male", "evan", "nathan", "tom", "alex", "aaron", "jamie", "oliver", "daniel", "arthur", "lee", "gordon", "aman", "rishi", "david", "mark", "george", "richard", "ravi", "sean", "google us english 4 (natural)", "google us english 3 (natural)", "google us english 6 (natural)", "google uk english 1 (natural)", "google uk english 3 (natural)", "google uk english 5 (natural)", "google australian english 2 (natural)", "google australian english 4 (natural)", "chrome os australian english 5", "android speech recognition and synthesis from google en-in-x-end-network", "android speech recognition and synthesis from google en-in-x-ene-network"] },
  "es": { label: "Spanish", native: "Español", prefixes: ["es"], female: ["elvira", "dalia", "elena", "sofia", "catalina", "ximena", "salome", "maria", "belkys", "andrea", "lorena", "paloma", "marta", "teresa", "karla", "yolanda", "margarita", "tania", "camila", "karina", "ramona", "valentina", "paola", "google español de estados unidos", "marisol", "mónica", "angelica", "paulina", "isabela", "francisca", "soledad", "jimena", "helena", "laura", "sabina", "google español 4 (natural)", "google español 1 (natural)", "google español 2 (natural)", "google español de estados unidos 1 (natural)", "google español de estados unidos 2 (natural)"], male: ["alvaro", "jorge", "tomas", "marcelo", "lorenzo", "gonzalo", "juan", "manuel", "luis", "rodrigo", "alonso", "andres", "javier", "carlos", "federico", "roberto", "mario", "alex", "victor", "emilio", "mateo", "sebastian", "google español", "diego", "pablo", "raul", "google español 3 (natural)", "google español 5 (natural)", "google español de estados unidos 3 (natural)", "google español de estados unidos 4 (natural)"] },
  "zh": { label: "Mandarin Chinese", native: "中文", prefixes: ["zh", "cmn"], female: ["xiaoxiao", "xiaoyi", "yunxi", "yunxia", "xiaobei", "xiaoni", "hsiaochen", "hsiaoyu", "google 普通话（中国大陆）", "google 國語（臺灣）", "lilian", "tiantian", "shasha", "lili", "lisheng", "lanlan", "shanshan", "yue", "tingting", "yu-shu", "dongmei", "panpan", "meijia", "huihui", "yaoyao", "yating", "hanhan", "android speech recognition and synthesis from google cmn-cn-x-ccc-network", "android speech recognition and synthesis from google cmn-cn-x-ssa-network", "android speech recognition and synthesis from google cmn-tw-x-ctc-network"], male: ["yunjian", "yunyang", "yunjhe", "han", "bobo", "taotao", "binbin", "li-mu", "haohao", "kangkang", "zhiwei", "android speech recognition and synthesis from google cmn-cn-x-ccd-network", "android speech recognition and synthesis from google cmn-cn-x-cce-network", "android speech recognition and synthesis from google cmn-tw-x-ctd-network", "android speech recognition and synthesis from google cmn-tw-x-cte-network"] },
  "hi": { label: "Hindi", native: "हिन्दी", prefixes: ["hi"], female: ["swara", "google हिन्दी", "kiyara", "lekha", "kalpana", "google हिन्दी 1 (natural)", "google हिन्दी 2 (natural)", "chrome os हिन्दी 1"], male: ["madhur", "neel", "hemant", "google हिन्दी 3 (natural)", "google हिन्दी 4 (natural)"] },
  "ar": { label: "Arabic", native: "العربية", prefixes: ["ar"], female: ["amina", "laila", "salma", "rana", "sana", "noura", "layla", "iman", "mouna", "aysha", "amal", "zariyah", "amany", "reem", "fatima", "maryam", "mariam", "hoda", "android speech recognition and synthesis from google ar-xa-x-arc-network", "android speech recognition and synthesis from google ar-xa-x-arz-network"], male: ["ismael", "ali", "shakir", "bassel", "taim", "fahed", "rami", "omar", "jamal", "abdullah", "moaz", "hamed", "laith", "hedi", "hamdan", "saleh", "tarik", "majed", "naayf", "android speech recognition and synthesis from google ar-xa-x-ard-network", "android speech recognition and synthesis from google ar-xa-x-are-network"] },
  "fr": { label: "French", native: "Français", prefixes: ["fr"], female: ["viviennemultilingual", "denise", "charline", "ariane", "eloise", "sylvie", "google français", "audrey", "aurélie", "marie", "aude", "chantal", "amélie", "julie", "hortence", "caroline", "google français 4 (natural)", "google français 2 (natural)", "google français 1 (natural)", "android speech recognition and synthesis from google fr-ca-x-caa-network", "android speech recognition and synthesis from google fr-ca-x-cac-network"], male: ["remymultilingual", "henri", "gerard", "fabrice", "antoine", "jean", "thierry", "thomas", "nicolas", "paul", "claude", "google français 5 (natural)", "google français 3 (natural)", "android speech recognition and synthesis from google fr-ca-x-cab-network", "android speech recognition and synthesis from google fr-ca-x-cad-network"] },
  "pt": { label: "Portuguese", native: "Português", prefixes: ["pt"], female: ["raquel", "francisca", "thalitamultilingual", "google português do brasil", "catarina", "joana", "fernanda", "luciana", "helia", "maria", "google português de portugal 1 (natural)", "google português de portugal 4 (natural)", "google português do brasil 1 (natural)", "google português do brasil 3 (natural)"], male: ["duarte", "antonio", "joaquim", "felipe", "daniel", "google português de portugal 2 (natural)", "google português de portugal 3 (natural)", "google português do brasil 2 (natural)"] },
  "ru": { label: "Russian", native: "Русский", prefixes: ["ru"], female: ["svetlana", "ekaterina", "google русский", "katya", "milena", "irina", "android speech recognition and synthesis from google ru-ru-x-dfc-network", "android speech recognition and synthesis from google ru-ru-x-ruc-network", "android speech recognition and synthesis from google ru-ru-x-rue-network"], male: ["dmitry", "yuri", "pavel", "android speech recognition and synthesis from google ru-ru-x-rud-network", "android speech recognition and synthesis from google ru-ru-x-ruf-network"] },
  "ja": { label: "Japanese", native: "日本語", prefixes: ["ja"], female: ["nanami", "google 日本語", "o-ren", "kyoko", "ayumi", "haruka", "google 日本語 1 (natural)", "chrome os 日本語 2"], male: ["keita", "hattori", "otoya", "ichiro", "google 日本語 2 (natural)", "google 日本語 3 (natural)"] },
  "de": { label: "German", native: "Deutsch", prefixes: ["de"], female: ["seraphinamultilingual", "amala", "katja", "ingrid", "leni", "google deutsch", "petra", "anna", "helena", "hedda", "google deutsch 2 (natural)", "google deutsch 1 (natural)"], male: ["florianmultilingual", "conrad", "killian", "jonas", "jan", "markus", "viktor", "yannick", "martin", "stefan", "michael", "karsten", "google deutsch 3 (natural)", "google deutsch 4 (natural)"] },
};

/* ---------- mentor system: two animated tutors, 10 languages, real AI Q&A ----------
 * Two tutor characters (Max / Nova) instead of a big persona roster. A
 * global narration-language selector (rendered on the Guide landing page)
 * controls "Read aloud" and the written subtitle on every role page at
 * once. Voice matching is hard-enforced: a voice is only ever used if
 * it's a confirmed match for the selected language AND the tutor's
 * gender (checked against LANG_VOICE_DB, a real named-voice catalog
 * sourced from the community-maintained readium/speech project) --
 * narration disables with an honest reason instead of ever guessing.
 * "Ask a question" answers for real if a visitor adds their own
 * Anthropic API key (stored only in their browser, calling Anthropic
 * directly -- never sent anywhere else, never paid for by this site);
 * without a key it falls back to matching the question, in English
 * only, against that role's own content.
 */
const TUTORS = [
  { id: "max", gender: "male", name: "Max" },
  { id: "nova", gender: "female", name: "Nova" },
];
const MENTOR_COLORS = [
  "var(--accent)", "var(--accent-2)", "var(--growth)", "var(--stability)", "var(--short)",
  "var(--nextgen)", "var(--funds)", "var(--pos)", "var(--neg)", "#6FA8DC", "#F2C14E", "#C792EA", "#FF5C72",
];

function escapeMentorHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// A JARVIS-style holographic projection, not an illustrated face -- two
// counter-rotating rings, a soft pulsing core, and a small three-bar
// waveform at the center that comes alive with ".speaking" instead of an
// animated mouth. Deliberately identical for both tutors (gender lives in
// the name/voice, not the avatar).
function charAvatarSVG(gender, color) {
  return `<svg viewBox="0 0 64 64" width="64" height="64">
    <circle class="holo-ring-outer" cx="32" cy="32" r="27" fill="none" stroke="${color}" stroke-width="1.2" stroke-dasharray="2.5 5" opacity="0.55"></circle>
    <circle class="holo-ring-mid" cx="32" cy="32" r="20" fill="none" stroke="${color}" stroke-width="1.5" stroke-dasharray="9 4" opacity="0.75"></circle>
    <circle class="holo-core" cx="32" cy="32" r="12" fill="${color}" opacity="0.16"></circle>
    <circle cx="32" cy="32" r="12" fill="none" stroke="${color}" stroke-width="1" opacity="0.6"></circle>
    <g class="holo-bars">
      <rect class="holo-bar holo-bar-1" x="27.2" y="28" width="2.2" height="8" rx="1.1" fill="${color}"></rect>
      <rect class="holo-bar holo-bar-2" x="30.9" y="25" width="2.2" height="14" rx="1.1" fill="${color}"></rect>
      <rect class="holo-bar holo-bar-3" x="34.6" y="28" width="2.2" height="8" rx="1.1" fill="${color}"></rect>
    </g>
  </svg>`;
}

/* ---------- language + voice state (shared localStorage keys: a
   selection made on the landing page applies on every role page) ---------- */
const LANG_STORE_KEY = "guideLang.v1";
function loadGlobalLang() {
  try {
    const v = localStorage.getItem(LANG_STORE_KEY);
    if (v && LANG_VOICE_DB[v]) return v;
  } catch (e) {}
  return "en";
}
function saveGlobalLang(code) {
  try { localStorage.setItem(LANG_STORE_KEY, code); } catch (e) {}
}
let GLOBAL_LANG = loadGlobalLang();

function tutorStoreKey(roleId) { return "guideTutor.v1::" + roleId; }
function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}
function loadTutorForRole(roleId) {
  try {
    const v = localStorage.getItem(tutorStoreKey(roleId));
    if (v === "max" || v === "nova") return TUTORS.find((t) => t.id === v);
  } catch (e) {}
  return TUTORS[hashStr(roleId) % TUTORS.length];
}
function saveTutorForRole(roleId, tutorId) {
  try { localStorage.setItem(tutorStoreKey(roleId), tutorId); } catch (e) {}
}

function voiceGenderGuess(voiceName, langCode) {
  const name = voiceName.toLowerCase();
  const db = LANG_VOICE_DB[langCode];
  if (db) {
    if (db.female.some((tok) => name.includes(tok) || tok.includes(name))) return "female";
    if (db.male.some((tok) => name.includes(tok) || tok.includes(name))) return "male";
  }
  if (/\bfemale\b|\bwoman\b/.test(name)) return "female";
  if (/\bmale\b|\bman\b/.test(name)) return "male";
  return null;
}
function voiceQualityScore(name) {
  const n = name.toLowerCase();
  let score = 0;
  if (n.includes("neural")) score += 3;
  if (n.includes("online")) score += 2;
  if (n.includes("natural")) score += 2;
  if (n.includes("multilingual")) score += 1;
  return score;
}
function pickVoiceFor(langCode, gender) {
  if (!("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices() || [];
  const db = LANG_VOICE_DB[langCode];
  if (!db) return null;
  const prefixes = db.prefixes.map((p) => p.toLowerCase());
  const langMatches = voices.filter((v) => v.lang && prefixes.some((p) => v.lang.toLowerCase().startsWith(p)));
  const confirmed = langMatches.filter((v) => voiceGenderGuess(v.name, langCode) === gender);
  if (confirmed.length === 0) return null;
  confirmed.sort((a, b) => voiceQualityScore(b.name) - voiceQualityScore(a.name));
  return confirmed[0];
}

const MENTOR_PANEL_REGISTRY = new Map(); // roleId -> { tutor, speakBtn, noteEl, subtitleEl }
let MENTOR_SPEAKING_ENTRY = null;

function refreshSpeakButtonState(entry) {
  const { tutor, speakBtn, noteEl } = entry;
  if (MENTOR_SPEAKING_ENTRY === entry) return;
  const langLabel = (LANG_VOICE_DB[GLOBAL_LANG] || {}).label || GLOBAL_LANG;
  if (!("speechSynthesis" in window)) {
    speakBtn.disabled = true;
    speakBtn.innerHTML = "&#128264; Read aloud";
    speakBtn.title = "Spoken narration isn't supported in this browser.";
    noteEl.textContent = "This browser doesn't support spoken narration (the Web Speech API) -- the subtitle text below still works fine.";
    return;
  }
  const voice = pickVoiceFor(GLOBAL_LANG, tutor.gender);
  if (voice) {
    speakBtn.disabled = false;
    speakBtn.innerHTML = "&#128264; Read aloud";
    speakBtn.title = "";
    noteEl.textContent = "";
  } else {
    speakBtn.disabled = true;
    speakBtn.innerHTML = "&#128263; No " + tutor.gender + " " + langLabel + " voice here";
    speakBtn.title = "This browser/device has no confirmed " + tutor.gender + " " + langLabel + " voice installed.";
    noteEl.textContent = "This browser/device doesn't have a confirmed " + tutor.gender + " " + langLabel + " voice installed, so spoken narration is off here rather than guessing. Try Chrome or Edge, or switch tutor/language, or just read the subtitle below.";
  }
}
function refreshAllMentorButtons() {
  MENTOR_PANEL_REGISTRY.forEach(refreshSpeakButtonState);
}
function stopMentorSpeech() {
  try { window.speechSynthesis && window.speechSynthesis.cancel(); } catch (e) {}
  const entry = MENTOR_SPEAKING_ENTRY;
  MENTOR_SPEAKING_ENTRY = null;
  if (entry) {
    entry.speakBtn.classList.remove("speaking");
    if (entry.waveEl) entry.waveEl.classList.remove("speaking");
    refreshSpeakButtonState(entry);
  }
}
function speakText(entry, text) {
  if (!("speechSynthesis" in window)) return;
  if (MENTOR_SPEAKING_ENTRY === entry) { stopMentorSpeech(); return; }
  stopMentorSpeech();
  const voice = pickVoiceFor(GLOBAL_LANG, entry.tutor.gender);
  if (!voice) { refreshSpeakButtonState(entry); return; }
  const utter = new SpeechSynthesisUtterance(text);
  utter.voice = voice;
  entry.noteEl.textContent = "Voice: " + voice.name + " (" + voice.lang + ") -- confirmed " + entry.tutor.gender + " " + (LANG_VOICE_DB[GLOBAL_LANG] || {}).label + ".";
  utter.onend = () => stopMentorSpeech();
  utter.onerror = () => stopMentorSpeech();
  MENTOR_SPEAKING_ENTRY = entry;
  entry.speakBtn.classList.add("speaking");
  if (entry.waveEl) entry.waveEl.classList.add("speaking");
  entry.speakBtn.innerHTML = "&#9632; Stop";
  window.speechSynthesis.speak(utter);
}

/* ---------- Q&A engine: English-only keyword match against a role's own
 * built-in expertise, passed in as an explicit {lead, text}[] knowledge
 * base (built by role-page.js from careers.json's prose plus its deeper
 * expertiseQA entries -- comp by level, lifestyle, core technical
 * mechanics). This is the only way "Ask a question" is answered; there
 * is no live API call to fall back from. ---------- */
const MENTOR_STOPWORDS = new Set(["the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be", "been",
  "being", "of", "to", "in", "on", "at", "for", "with", "about", "as", "by", "from", "into", "over", "after",
  "before", "between", "this", "that", "these", "those", "it", "its", "i", "you", "your", "they", "them", "their",
  "he", "she", "his", "her", "do", "does", "did", "doing", "have", "has", "had", "having", "what", "when", "where",
  "why", "how", "who", "which", "can", "could", "would", "should", "will", "shall", "my", "me", "we", "us", "our",
  "so", "if", "than", "then", "there", "not", "no", "yes", "just", "really", "actually", "like", "get", "got",
  "much", "many", "more", "most"]);
const MENTOR_SYNONYMS = {
  money: "paid", earn: "paid", earns: "paid", earning: "paid", earnings: "paid",
  make: "paid", makes: "paid", making: "paid", salary: "paid", salaries: "paid",
  income: "paid", wage: "paid", wages: "paid", pay: "paid", pays: "paid", paying: "paid",
  compensation: "paid", bonus: "paid", bonuses: "paid", cost: "paid", costs: "paid", fee: "paid", fees: "paid",
};
function mentorTokenize(text) {
  return (text.toLowerCase().match(/[a-z']+/g) || [])
    .filter((w) => w.length > 2 && !MENTOR_STOPWORDS.has(w))
    .map((w) => MENTOR_SYNONYMS[w] || w);
}
// Loose stem match (plural/verb-form tolerant) so "LBOs"/"works" still
// matches an entry written as "LBO"/"work" -- a short common prefix with a
// small length difference, not a real stemmer, same spirit as the voice
// name matching elsewhere in this file (includes()-style, not exact-only).
function tokensMatch(a, b) {
  if (a === b) return true;
  const shorter = a.length <= b.length ? a : b;
  const longer = a.length <= b.length ? b : a;
  return shorter.length >= 3 && longer.startsWith(shorter) && longer.length - shorter.length <= 2;
}
// Ranks by how many DISTINCT question concepts an entry covers first, then
// by total match frequency as a tiebreak only within that. Plain frequency
// alone lets one generic, repeated word (e.g. several incidental "risk"
// mentions) beat an entry that actually covers more of what was asked --
// distinct-coverage-first fixes that while still preferring, among equally
// on-topic entries, the one that discusses the topic more.
function bestMentorMatch(entries, qTokenSet) {
  let best = null, bestDistinct = 0, bestRaw = 0;
  for (const entry of entries) {
    const entryTokens = mentorTokenize(entry.lead + " " + entry.text);
    let distinct = 0, raw = 0;
    for (const t of qTokenSet) {
      let count = 0;
      for (const et of entryTokens) if (tokensMatch(et, t)) count++;
      if (count > 0) { distinct++; raw += count; }
    }
    if (distinct > bestDistinct || (distinct === bestDistinct && raw > bestRaw)) {
      best = entry; bestDistinct = distinct; bestRaw = raw;
    }
  }
  return best;
}
// kb: [{lead, text, generic?}] -- plain-text strings (HTML already stripped
// by the caller) describing the role, used for a crude keyword match.
function answerMentorQuestionStatic(kb, question) {
  const qTokenSet = new Set(mentorTokenize(question));
  if (qTokenSet.size === 0) return null;
  const match = bestMentorMatch(kb.filter((e) => !e.generic), qTokenSet)
    || bestMentorMatch(kb.filter((e) => e.generic), qTokenSet);
  return match ? match.lead + " " + match.text : null;
}

/* ---------- real-company lookup: the Market Scanner's own daily-refreshed
 * data, not a per-question internet fetch. This site has no backend, so
 * "ask about a real company" is answered from dashboard/data.json -- the
 * same 116-ticker file the Scanner page shows, refreshed daily by a
 * WebSearch-grounded routine and committed to the repo, not invented or
 * looked up live. If a question names a company outside that 116-ticker
 * universe, this returns null and the caller falls back to (or combines
 * with) the role's own written knowledge base -- it never fakes a number
 * for a company this site doesn't actually track.
 */
const CATEGORY_LABELS = {
  growth: "Biggest Growth desk", stability: "Stability desk", nextgen: "Next-Gen Growth desk",
  shorts: "Short Candidates desk", funds: "Funds & Company Size desk",
};
let SCANNER_DATA_PROMISE = null;
let TICKER_INDEX = null;   // "NVDA" -> { item, category }
let NAME_INDEX = null;     // [{ alias, item, category }], longest alias first
let SCANNER_GENERATED = null;

// Strips legal-entity/generic suffix words so "Palantir Technologies"
// yields the alias people actually type ("palantir"), and normalizes
// punctuation (periods, commas, apostrophes, ".com") so "McDonald's" /
// "mcdonalds" and "Amazon.com" / "amazon" both compare equal.
const NAME_SUFFIX_WORDS = new Set(["inc", "corporation", "corp", "company", "co", "group",
  "holdings", "holding", "limited", "ltd", "technologies", "technology", "therapeutics",
  "pharmaceuticals", "platforms", "international", "industries", "worldwide", "entertainment",
  "interactive", "global", "systems", "solutions", "ventures", "and", "&"]);
function normalizeCompanyText(s) {
  return String(s).toLowerCase().replace(/\.com\b/g, " ").replace(/[.,'"]/g, "")
    .replace(/\s+/g, " ").trim();
}
function aliasWords(name) {
  const words = normalizeCompanyText(name).replace(/^the\s+/, "").split(" ");
  while (words.length > 1 && NAME_SUFFIX_WORDS.has(words[words.length - 1])) words.pop();
  return words;
}

function loadScannerData() {
  if (SCANNER_DATA_PROMISE) return SCANNER_DATA_PROMISE;
  const base = (window.SITE_NAV && window.SITE_NAV.base) || "";
  SCANNER_DATA_PROMISE = fetch(base + "data.json")
    .then((res) => res.json())
    .then((data) => {
      TICKER_INDEX = {};
      const aliasOwners = {}; // alias -> ticker, to detect/drop ambiguous short aliases (e.g. "vanguard")
      const candidates = []; // [{alias, item, category}]
      SCANNER_GENERATED = data.generated || "recently";
      for (const [category, items] of Object.entries(data.categories || {})) {
        for (const item of items) {
          TICKER_INDEX[item.ticker] = { item, category };
          if (!item.name) continue;
          const words = aliasWords(item.name);
          const aliases = new Set([words.join(" "), words[0]]);
          for (const alias of aliases) {
            if (alias.length < 4) continue;
            if (aliasOwners[alias] && aliasOwners[alias] !== item.ticker) {
              aliasOwners[alias] = "AMBIGUOUS";
              continue;
            }
            aliasOwners[alias] = item.ticker;
            candidates.push({ alias, item, category });
          }
        }
      }
      NAME_INDEX = candidates.filter((c) => aliasOwners[c.alias] !== "AMBIGUOUS");
      NAME_INDEX.sort((a, b) => b.alias.length - a.alias.length);
      return data;
    })
    .catch(() => null);
  return SCANNER_DATA_PROMISE;
}

// Multi-letter tickers (3+) match case-insensitively; 1-2 letter tickers
// (several real ones here: V, O, T, W, GE) only match if typed in the
// exact uppercase a visitor would use for a ticker, not an ordinary word.
function findCompanyMention(question) {
  if (!TICKER_INDEX) return null;
  const words = question.match(/[A-Za-z]+/g) || [];
  for (const w of words) {
    const upper = w.toUpperCase();
    const hit = TICKER_INDEX[upper];
    if (hit && (upper.length >= 3 || w === upper)) return hit;
  }
  const qNorm = normalizeCompanyText(question);
  for (const entry of NAME_INDEX) {
    if (qNorm.includes(entry.alias)) return { item: entry.item, category: entry.category };
  }
  return null;
}

function formatCompanyAnswer(hit) {
  const { item, category } = hit;
  const bits = [`${item.ticker} (${item.name}) is trading around $${Number(item.price).toFixed(2)}`];
  if (item.mktCap) bits.push(`market cap ${item.mktCap}`);
  if (item.metric_label && item.metric != null) {
    const isPct = typeof item.metric === "number" && !/beta/i.test(item.metric_label);
    bits.push(`${item.metric_label.toLowerCase()}: ${item.metric}${isPct ? "%" : ""}`);
  }
  const ratingBit = item.rating ? ` Current read: ${item.rating}.` : "";
  const deskLabel = CATEGORY_LABELS[category] || category;
  return `Real data from this site's Market Scanner (${deskLabel}, refreshed ${SCANNER_GENERATED}): ${bits.join(", ")}.${ratingBit} ${item.blurb || ""}`.trim();
}

/* ---------- rendering: one mentor panel per role page ----------
 * mountEl: the element the panel is inserted into (as its first child).
 * kb: [{lead, text, generic?}] plain-text knowledge base for the static
 * fallback Q&A (role-page.js builds this straight from careers.json).
 */
function renderMentorPanel(mountEl, roleId, roleTitle, kb, colorIdx) {
  const existing = mountEl.querySelector(".mentor-panel");
  if (existing) existing.remove();
  MENTOR_PANEL_REGISTRY.delete(roleId);

  const tutor = loadTutorForRole(roleId);
  const color = MENTOR_COLORS[(colorIdx || 0) % MENTOR_COLORS.length];
  const narrationMap = ROLE_NARRATION[roleId] || {};
  const subtitleText = narrationMap[GLOBAL_LANG] || narrationMap.en || "";
  const langMeta = LANG_VOICE_DB[GLOBAL_LANG] || LANG_VOICE_DB.en;

  const panel = document.createElement("div");
  panel.className = "mentor-panel";
  panel.style.setProperty("--mc", color);
  panel.innerHTML = `
    <div class="mentor-avatar">${charAvatarSVG(tutor.gender, color)}</div>
    <div class="mentor-info">
      <div class="mentor-tag">Holographic tutor</div>
      <div class="mentor-name">${tutor.name}</div>
      <div class="mentor-sub">${tutor.gender === "male" ? "Male" : "Female"} tutor &middot; narrating in ${escapeMentorHtml(langMeta.label)}${langMeta.native !== langMeta.label ? " (" + escapeMentorHtml(langMeta.native) + ")" : ""}</div>
      <p class="mentor-subtitle" lang="${GLOBAL_LANG}">${escapeMentorHtml(subtitleText)}</p>
      <div class="mentor-actions">
        <button type="button" class="mentor-btn speak-btn">&#128264; Read aloud</button>
        <button type="button" class="mentor-btn switch-tutor-btn">&#8635; Switch tutor</button>
      </div>
      <div class="mentor-voice-note"></div>
      <div class="mentor-ask">
        <div class="mentor-ask-label">Ask ${escapeMentorHtml(tutor.name)} a question &mdash; name a real company for today's actual numbers, or ask about comp, hours, or how the job's technical side works</div>
        <div class="mentor-ask-row">
          <input type="text" class="mentor-ask-input" placeholder="e.g. what's NVDA's price today, or how do LBOs work?">
          <button type="button" class="mentor-btn ask-btn">Ask</button>
        </div>
        <div class="mentor-answer" style="display:none"></div>
      </div>
    </div>`;

  mountEl.insertBefore(panel, mountEl.firstChild);
  loadScannerData(); // warm the cache so the first "ask" doesn't wait on it

  const entry = {
    tutor, speakBtn: panel.querySelector(".speak-btn"), noteEl: panel.querySelector(".mentor-voice-note"),
    subtitleEl: panel.querySelector(".mentor-subtitle"), waveEl: panel.querySelector(".holo-bars"),
  };
  MENTOR_PANEL_REGISTRY.set(roleId, entry);
  entry.speakBtn.addEventListener("click", () => speakText(entry, subtitleText));
  refreshSpeakButtonState(entry);

  panel.querySelector(".switch-tutor-btn").addEventListener("click", () => {
    stopMentorSpeech();
    const other = TUTORS.find((t) => t.id !== tutor.id);
    saveTutorForRole(roleId, other.id);
    renderMentorPanel(mountEl, roleId, roleTitle, kb, colorIdx);
  });

  const askInput = panel.querySelector(".mentor-ask-input");
  const answerBox = panel.querySelector(".mentor-answer");
  const askBtn = panel.querySelector(".ask-btn");

  function renderAnswer(q, text, srcNote) {
    answerBox.innerHTML = `<div class="mentor-answer-q">You asked: &ldquo;${escapeMentorHtml(q)}&rdquo;</div>${escapeMentorHtml(text)}` +
      (srcNote ? `<div class="mentor-answer-src">${escapeMentorHtml(srcNote)}</div>` : "") +
      `<br><button type="button" class="mentor-answer-speak">&#128264; Read this answer aloud</button>`;
    const answerSpeakBtn = answerBox.querySelector(".mentor-answer-speak");
    const answerEntry = { tutor, speakBtn: answerSpeakBtn, noteEl: document.createElement("div") };
    refreshSpeakButtonState(answerEntry);
    answerSpeakBtn.addEventListener("click", () => speakText(answerEntry, text));
  }

  function answerAndMaybeTieIn(q, companyAnswer) {
    const kbMatch = answerMentorQuestionStatic(kb, q);
    const tieIn = kbMatch ? ` As a ${roleTitle.toLowerCase()}, that's exactly the kind of figure I'd be looking at.` : "";
    renderAnswer(q, companyAnswer + tieIn, "Real Scanner data, not a guess -- refreshed daily from this site's own data.json, covering the 116 companies tracked here.");
  }

  function submitAsk() {
    const q = askInput.value.trim();
    if (!q) return;
    answerBox.style.display = "block";
    answerBox.innerHTML = `<div class="mentor-answer-q">You asked: &ldquo;${escapeMentorHtml(q)}&rdquo;</div>Checking this site's own market data&hellip;`;
    loadScannerData().then(() => {
      const hit = findCompanyMention(q);
      if (hit) {
        answerAndMaybeTieIn(q, formatCompanyAnswer(hit));
        return;
      }
      const match = answerMentorQuestionStatic(kb, q);
      if (match) {
        renderAnswer(q, match, "English only -- matched against everything " + tutor.name + " knows about this role.");
      } else {
        renderAnswer(q, "I don't have anything on that specific question for this role -- try naming one of the 116 companies this site tracks for real numbers, or ask about comp by level, hours and time off, how I use the market day to day, or the technical mechanics behind the job (like how an LBO or a DCF actually works).", "");
      }
    });
  }
  askBtn.addEventListener("click", submitAsk);
  askInput.addEventListener("keydown", (e) => { if (e.key === "Enter") submitAsk(); });
}

/* ---------- global controls (rendered on the landing page only) ---------- */
function wireLangSelector(onChange) {
  const sel = document.getElementById("globalLangSelect");
  if (!sel) return;
  sel.innerHTML = Object.keys(LANG_VOICE_DB).map((code) => {
    const v = LANG_VOICE_DB[code];
    return `<option value="${code}" ${code === GLOBAL_LANG ? "selected" : ""}>${escapeMentorHtml(v.label)} (${escapeMentorHtml(v.native)})</option>`;
  }).join("");
  sel.addEventListener("change", () => {
    stopMentorSpeech();
    GLOBAL_LANG = sel.value;
    saveGlobalLang(GLOBAL_LANG);
    if (onChange) onChange();
  });
}

function initMentorVoices() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = refreshAllMentorButtons;
    setTimeout(refreshAllMentorButtons, 350);
  }
}
window.addEventListener("beforeunload", stopMentorSpeech);
