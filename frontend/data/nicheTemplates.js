(function () {
  const AUTOSOCIAL_NICHES_CONFIG_V1 = 'AUTOSOCIAL_NICHES_CONFIG_V1';
  const nicheList = [
    {
      id: 'smm_marketing',
      label: 'SMM и маркетинг',
      aliases: ['smm', 'маркетинг', 'smm и маркетинг'],
      keywords: ['контент', 'лиды', 'воронка', 'продвижение', 'соцсети', 'контент-план'],
      audience: 'Малый бизнес, эксперты и бренды, которым нужен понятный поток контента и заявок.',
      painPoints: ['Нет стабильного контент-плана', 'Посты не приводят к заявкам', 'Контент делается хаотично и вручную'],
      contentAngles: ['разбор ошибок', 'быстрые практики', 'кейсы и результаты', 'простые фреймворки', 'развенчание мифов'],
      topicTemplates: [
        'Почему контент-план не работает без одной ключевой метрики',
        '3 ошибки в SMM, из-за которых подписчики не становятся клиентами',
        'Как малому бизнесу публиковаться регулярно без большой команды',
        'Что писать в соцсетях, когда кажется, что темы закончились',
        'Как превратить экспертный контент в заявки, а не в пустые лайки',
        'Почему контент без оффера не приводит к продажам',
        'Как выбрать рубрики, которые реально держат внимание аудитории',
        '5 признаков, что ваш SMM работает хаотично',
        'Что публиковать, если вы продаёте сложную услугу',
        'Как упростить путь клиента от поста до сообщения',
        'Почему полезный контент иногда не продаёт и что с этим делать',
        'Как понять, что вашей аудитории пора показать кейс, а не совет',
      ],
      hookTemplates: [
        'Если контент есть, а заявок нет, проблема обычно не в охватах.',
        'Большинство бизнесов теряют клиентов не из-за алгоритмов, а из-за хаоса в коммуникации.',
        'Контент начинает продавать, когда каждый пост ведёт к следующему шагу клиента.',
      ],
      ctaTemplates: [
        'Напишите «КОНТЕНТ», и мы поможем собрать понятную систему публикаций.',
        'Сохраните пост и проверьте, есть ли у вас эти ошибки в контенте.',
        'Напишите в сообщения, если хотите разобрать контент под ваш бизнес.',
      ],
      offerTemplates: ['аудит контента', 'контент-план на месяц', 'разбор воронки сообщений'],
      bannedCrossNicheWords: ['барбер', 'косметолог', 'автосервис', 'детейлинг', 'полнолуние', 'карма'],
    },
    {
      id: 'cosmetology',
      label: 'Косметология',
      aliases: ['косметология', 'косметолог'],
      keywords: ['кожа', 'уход', 'процедуры', 'лицо', 'омоложение', 'чистка'],
      audience: 'Женщины и мужчины, которые хотят ухоженную кожу и понятный план процедур без стресса.',
      painPoints: ['Страшно выбрать процедуру', 'Много мифов об уходе', 'Нет понимания, что подходит именно коже клиента'],
      contentAngles: ['мифы и факты', 'уход между процедурами', 'подготовка к визиту', 'результат и восстановление', 'разбор частых вопросов'],
      topicTemplates: [
        'Как понять, какая процедура действительно нужна вашей коже',
        '3 ошибки домашнего ухода, которые портят результат процедур',
        'Что важно знать перед первой консультацией у косметолога',
        'Почему чувствительная кожа требует другого подхода',
        'Какие привычки ускоряют обезвоживание кожи',
        'Что делать, чтобы эффект после процедуры держался дольше',
        'Как выбрать курс процедур без лишних трат',
        'Можно ли совмещать активный домашний уход и косметологию',
        'Как понять, что коже не хватает восстановления, а не новых средств',
        'Почему кожа может реагировать на стресс сильнее, чем на уход',
      ],
      hookTemplates: [
        'Кожа редко “капризничает” просто так — обычно она сигнализирует о перегрузе или неправильном уходе.',
        'Одна правильно подобранная процедура даёт больше пользы, чем десяток случайных баночек.',
        'Хорошая косметология начинается не с модной процедуры, а с понимания состояния кожи.',
      ],
      ctaTemplates: [
        'Напишите «КОЖА», и мы подскажем, с чего лучше начать уход.',
        'Сохраните пост, чтобы свериться с этими признаками перед записью.',
        'Напишите в сообщения, если хотите подобрать процедуры под вашу кожу.',
      ],
      offerTemplates: ['диагностика кожи', 'персональный план ухода', 'подбор курса процедур'],
      bannedCrossNicheWords: ['барбер', 'двигатель', 'луна', 'карма', 'квартира'],
    },
    {
      id: 'barbershop',
      label: 'Барбершоп',
      aliases: ['барбершоп', 'барбер'],
      keywords: ['стрижка', 'борода', 'мужской стиль', 'уход', 'барбер'],
      audience: 'Мужчины, которые хотят выглядеть аккуратно, уверенно и без лишней суеты.',
      painPoints: ['Неясно, какая стрижка подойдёт', 'Есть страх попасть не к своему мастеру', 'Нет времени на долгие эксперименты'],
      contentAngles: ['уход за бородой', 'выбор формы стрижки', 'частые ошибки дома', 'стиль под образ жизни', 'уверенность после ухода'],
      topicTemplates: [
        'Как выбрать стрижку, которая подходит именно вашей форме лица',
        'Почему борода без ухода быстро теряет форму',
        '3 ошибки в домашней укладке, которые портят результат после барбера',
        'Как понять, что пора обновить стрижку, а не терпеть “ещё неделю”',
        'Что обсудить с барбером, чтобы получить нужный результат с первого раза',
        'Как сохранить форму бороды между визитами',
        'Какие привычки делают мужской образ аккуратным каждый день',
        'Почему регулярный уход выглядит лучше редких радикальных стрижек',
        'Как подобрать уход для волос и бороды без лишних банок',
        'Что важнее для уверенного образа: форма, длина или уход',
      ],
      hookTemplates: [
        'Хорошая стрижка работает каждый день, а не только в день визита.',
        'Большинство проблем с бородой начинаются не в кресле барбера, а дома.',
        'Правильный мужской уход — это не про сложность, а про системность.',
      ],
      ctaTemplates: [
        'Напишите «СТИЛЬ», и мы подскажем, какой формат ухода подойдёт вам.',
        'Сохраните пост, чтобы обсудить это с барбером на следующем визите.',
        'Напишите в сообщения, если хотите подобрать стрижку под ваш образ.',
      ],
      offerTemplates: ['подбор образа', 'комплекс стрижка + борода', 'рекомендации по домашнему уходу'],
      bannedCrossNicheWords: ['кожа лица', 'двигатель', 'полнолуние', 'ремонт квартиры', 'лидогенерация'],
    },
    {
      id: 'autoservice',
      label: 'Автосервис',
      aliases: ['автосервис', 'сто', 'ремонт авто'],
      keywords: ['авто', 'диагностика', 'ремонт', 'обслуживание', 'масло', 'подвеска'],
      audience: 'Водители, которым нужна предсказуемая и честная забота о машине без лишних расходов.',
      painPoints: ['Страшно переплатить', 'Неясно, когда ехать на диагностику', 'Нет уверенности в качестве ремонта'],
      contentAngles: ['симптомы поломок', 'сезонное обслуживание', 'как подготовиться к визиту', 'на чём нельзя экономить', 'разбор частых ошибок'],
      topicTemplates: [
        '5 признаков, что машине нужна диагностика уже сейчас',
        'Почему откладывать небольшую поломку почти всегда дороже',
        'Что проверить в автомобиле перед дальней поездкой',
        'Как понять, что проблема в подвеске, а не “кажется”',
        'Какие звуки машины нельзя игнорировать',
        'Почему регулярная диагностика экономит деньги, а не наоборот',
        'Что спросить у мастера перед началом ремонта',
        'Как подготовить авто к сезону без лишних трат',
        'Какие ошибки водители чаще всего допускают после ремонта',
        'На чём в обслуживании машины нельзя экономить без последствий',
      ],
      hookTemplates: [
        'Машина почти всегда предупреждает заранее — важно не пропустить сигнал.',
        'Дороже всего обходится не ремонт, а привычка тянуть до последнего.',
        'Честный сервис начинается с понятной диагностики и прозрачных объяснений.',
      ],
      ctaTemplates: [
        'Напишите «АВТО», и мы подскажем, нужна ли вам диагностика.',
        'Сохраните пост, чтобы свериться с признаками перед поездкой в сервис.',
        'Напишите в сообщения, если хотите быстро понять следующий шаг по машине.',
      ],
      offerTemplates: ['экспресс-диагностика', 'сезонный чек-ап', 'подбор плана обслуживания'],
      bannedCrossNicheWords: ['борода', 'кожа лица', 'карма', 'медитация', 'ремонт кухни'],
    },
    {
      id: 'detailing',
      label: 'Детейлинг',
      aliases: ['детейлинг', 'детейлинг авто'],
      keywords: ['полировка', 'защита кузова', 'салон', 'керамика', 'автоуход'],
      audience: 'Автовладельцы, которые хотят сохранить вид машины, комфорт и ликвидность.',
      painPoints: ['Неясно, какая защита нужна', 'Есть страх переплатить за лишние услуги', 'Хочется дольше сохранить чистый и аккуратный вид авто'],
      contentAngles: ['защита кузова', 'уход за салоном', 'сезонные советы', 'до/после без преувеличений', 'долгосрочная выгода'],
      topicTemplates: [
        'Что даёт детейлинг, кроме красивого внешнего вида',
        'Как понять, нужна ли кузову защита прямо сейчас',
        'Почему обычная мойка не заменяет базовый уход за покрытием',
        'Как сохранить салон свежим и аккуратным дольше',
        'Какие привычки быстрее всего портят состояние кузова',
        'Зачем делать защиту кузова перед сезоном',
        'Как ухаживать за машиной после полировки',
        'Почему ухоженный автомобиль легче продать и выгоднее оценить',
        'Что выбрать: разовый уход или системную защиту авто',
        'Какие зоны машины чаще всего страдают от повседневной эксплуатации',
      ],
      hookTemplates: [
        'Детейлинг — это не только про блеск, а про сохранение состояния автомобиля.',
        'Красивый кузов — приятный бонус, но главная выгода в защите и ресурсе.',
        'Регулярный уход за авто всегда дешевле восстановления после запущенного состояния.',
      ],
      ctaTemplates: [
        'Напишите «ДЕТЕЙЛИНГ», и мы подскажем, какой уход нужен вашему авто.',
        'Сохраните пост, чтобы не потерять чек-лист по защите кузова.',
        'Напишите в сообщения, если хотите подобрать уход под сезон и состояние машины.',
      ],
      offerTemplates: ['диагностика покрытия', 'подбор защитного пакета', 'комплексный уход за салоном и кузовом'],
      bannedCrossNicheWords: ['борода', 'психолог', 'карма', 'маркетинговая воронка', 'новолуние'],
    },
    {
      id: 'apartment_renovation',
      label: 'Ремонт квартир',
      aliases: ['ремонт квартир', 'ремонт', 'отделка'],
      keywords: ['ремонт', 'квартира', 'отделка', 'дизайн', 'смета', 'черновые работы'],
      audience: 'Собственники квартир, которые хотят предсказуемый ремонт без хаоса, срывов и скрытых расходов.',
      painPoints: ['Страх выйти за бюджет', 'Непонятно, с чего начать', 'Есть опасение ошибок и переделок'],
      contentAngles: ['этапы ремонта', 'ошибки на старте', 'контроль бюджета', 'что спрашивать подрядчика', 'как избежать переделок'],
      topicTemplates: [
        'С чего начать ремонт квартиры, чтобы не потерять деньги на старте',
        'Какие ошибки в ремонте чаще всего приводят к переделкам',
        'Как заранее понять реальный бюджет ремонта',
        'Что обсудить с подрядчиком до подписания договора',
        'Почему отсутствие плана ремонта почти всегда ведёт к срыву сроков',
        'Какие решения лучше принять до начала черновых работ',
        'Как не потеряться в выборе материалов и не переплатить',
        'Что важно проверить после каждого этапа ремонта',
        'Почему экономия на отдельных работах потом выходит дороже',
        'Как сделать ремонт спокойнее и предсказуемее для семьи',
      ],
      hookTemplates: [
        'Ремонт начинает дорожать не из-за цен, а из-за решений без системы.',
        'Чем раньше появляется понятный план ремонта, тем меньше переделок и нервов.',
        'Хороший подрядчик упрощает ремонт, а не добавляет новых неизвестных.',
      ],
      ctaTemplates: [
        'Напишите «РЕМОНТ», и мы подскажем, с чего начать именно в вашей ситуации.',
        'Сохраните пост, чтобы свериться с ним перед стартом ремонта.',
        'Напишите в сообщения, если хотите разложить ремонт по этапам и бюджету.',
      ],
      offerTemplates: ['план ремонта', 'смета по этапам', 'консультация перед стартом работ'],
      bannedCrossNicheWords: ['интуиция', 'карма', 'борода', 'кожа лица', 'детейлинг'],
    },
    {
      id: 'psychology',
      label: 'Психология',
      aliases: ['психология', 'психолог'],
      keywords: ['эмоции', 'границы', 'тревога', 'самооценка', 'отношения', 'ресурс'],
      audience: 'Люди, которые хотят лучше понимать себя, снизить внутреннее напряжение и выстроить устойчивое состояние.',
      painPoints: ['Сложно справляться с тревогой', 'Есть повторяющиеся эмоциональные сценарии', 'Трудно отстаивать свои границы'],
      contentAngles: ['самонаблюдение', 'эмоции в быту', 'границы и отношения', 'бережные практики', 'понятные объяснения сложных состояний'],
      topicTemplates: [
        'Почему мы устаём не только физически, но и эмоционально',
        'Как понять, что тревога уже влияет на повседневную жизнь',
        '3 признака, что ваши личные границы регулярно нарушаются',
        'Почему повторяются одни и те же болезненные сценарии',
        'Как заметить первые сигналы внутреннего перегруза',
        'Что делать, если сложно говорить “нет” без чувства вины',
        'Почему отдых не помогает, если нервная система всё ещё в напряжении',
        'Как понять свои эмоциональные триггеры простыми шагами',
        'Что мешает чувствовать устойчивость даже при внешнем благополучии',
        'Как начать бережнее относиться к себе без резких изменений',
      ],
      hookTemplates: [
        'Иногда проблема не в “слабости”, а в том, что внутреннее напряжение копилось слишком долго.',
        'Психологическая устойчивость начинается с умения замечать своё состояние вовремя.',
        'Многие трудности повторяются не случайно — у них есть понятная внутренняя логика.',
      ],
      ctaTemplates: [
        'Напишите «ПОДДЕРЖКА», если хотите бережно разобрать свою ситуацию.',
        'Сохраните пост, чтобы вернуться к этим признакам в спокойный момент.',
        'Напишите в сообщения, если хотите подобрать формат психологической поддержки.',
      ],
      offerTemplates: ['первая консультация', 'разбор запроса', 'маршрут поддержки'],
      bannedCrossNicheWords: ['полнолуние', 'карма', 'двигатель', 'барбер', 'контент-воронка'],
    },
    {
      id: 'consulting',
      label: 'Консалтинг',
      aliases: ['консалтинг', 'консультирование', 'бизнес-консалтинг'],
      keywords: ['решения', 'стратегия', 'рост', 'процессы', 'аудит', 'эффективность'],
      audience: 'Руководители и собственники, которым нужны понятные решения, а не абстрактные советы.',
      painPoints: ['Сложно увидеть узкое место в бизнесе', 'Не хватает внешнего взгляда', 'Есть усталость от разрозненных действий без результата'],
      contentAngles: ['ошибки управления', 'ускорение решений', 'типовые узкие места', 'рост без хаоса', 'практичные изменения'],
      topicTemplates: [
        'Почему бизнес может буксовать даже при хорошем спросе',
        '3 сигнала, что в компании есть системное узкое место',
        'Как понять, где бизнес теряет деньги незаметно',
        'Почему быстрые решения без диагностики часто дают слабый эффект',
        'Что нужно проверить перед масштабированием бизнеса',
        'Как отличить рост от перегрузки команды и процессов',
        'Почему хорошие сотрудники не спасают слабую систему',
        'Как руководителю увидеть проблему раньше, чем она станет дорогой',
        'Какие вопросы помогают быстро найти точку роста',
        'С чего начать, если хочется навести порядок в бизнесе без хаоса',
      ],
      hookTemplates: [
        'Бизнес редко тормозит из-за одной большой ошибки — чаще из-за нескольких незаметных узких мест.',
        'Если команда много делает, а результат не ускоряется, проблема обычно системная.',
        'Хороший консалтинг нужен не для теории, а для понятных решений и скорости.',
      ],
      ctaTemplates: [
        'Напишите «АУДИТ», если хотите увидеть узкие места и точки роста.',
        'Сохраните пост, чтобы проверить эти сигналы в своём бизнесе.',
        'Напишите в сообщения, если хотите разобрать ситуацию без воды.',
      ],
      offerTemplates: ['диагностика бизнеса', 'стратегическая сессия', 'разбор процессов и точек роста'],
      bannedCrossNicheWords: ['полнолуние', 'борода', 'кожа лица', 'детейлинг', 'аффирмации'],
    },
    {
      id: 'online_courses',
      label: 'Онлайн-курсы',
      aliases: ['онлайн-курсы', 'онлайн курс', 'образование'],
      keywords: ['обучение', 'курс', 'уроки', 'результат', 'экспертность', 'программа'],
      audience: 'Люди, которые выбирают обучение и хотят понять, принесёт ли курс реальную пользу и результат.',
      painPoints: ['Сложно выбрать качественный курс', 'Есть усталость от обещаний без результата', 'Непонятно, как внедрить знания на практике'],
      contentAngles: ['результат обучения', 'ошибки выбора курса', 'как проходит обучение', 'что мешает внедрению', 'реальные кейсы учеников'],
      topicTemplates: [
        'Как понять, что онлайн-курс действительно даст результат',
        '3 признака, что программа обучения продумана, а не собрана наспех',
        'Почему знания без практики быстро забываются',
        'Что важно проверить перед покупкой онлайн-курса',
        'Как выбрать обучение под свою реальную задачу, а не под красивое обещание',
        'Почему даже хороший курс не работает без одного важного условия',
        'Как понять, что вам нужен наставник, а не только уроки',
        'Какие ошибки чаще всего мешают пройти обучение до результата',
        'Что отличает сильную образовательную программу от потока теории',
        'Как превратить обучение в понятный следующий шаг для себя или бизнеса',
      ],
      hookTemplates: [
        'Сильный курс продаёт не уроки, а путь к конкретному результату.',
        'Проблема большинства обучений не в объёме знаний, а в слабом внедрении.',
        'Перед покупкой курса важно понять не “что внутри”, а “что изменится после”.',
      ],
      ctaTemplates: [
        'Напишите «КУРС», если хотите подобрать программу под вашу задачу.',
        'Сохраните пост, чтобы свериться с этими признаками перед покупкой обучения.',
        'Напишите в сообщения, если хотите понять, какой формат обучения подойдёт именно вам.',
      ],
      offerTemplates: ['подбор программы', 'консультация по обучению', 'разбор цели и формата'],
      bannedCrossNicheWords: ['карма', 'барбер', 'авто', 'керамика', 'чистка лица'],
    },
    {
      id: 'fitness',
      label: 'Фитнес',
      aliases: ['фитнес', 'тренировки', 'тренер'],
      keywords: ['тренировки', 'форма', 'выносливость', 'похудение', 'мышцы', 'режим'],
      audience: 'Люди, которые хотят улучшить форму, самочувствие и дисциплину без крайностей и перегруза.',
      painPoints: ['Сложно начать регулярно', 'Нет результата от хаотичных тренировок', 'Мешают срывы и потеря мотивации'],
      contentAngles: ['старт без перегруза', 'ошибки новичков', 'система и привычки', 'форма и самочувствие', 'результат без крайностей'],
      topicTemplates: [
        'Почему регулярность в тренировках важнее идеального плана',
        '3 ошибки новичков, из-за которых прогресс быстро останавливается',
        'Как начать тренироваться без жёсткого режима и выгорания',
        'Что мешает видеть результат даже при старании',
        'Почему восстановление так же важно, как и сама тренировка',
        'Как понять, что вам нужен другой формат нагрузки',
        'Что делать, если мотивация к тренировкам быстро исчезает',
        'Как не сорваться после хорошего старта в фитнесе',
        'Почему маленькие шаги часто работают лучше, чем резкие обещания себе',
        'Как тренировки влияют не только на тело, но и на уровень энергии',
      ],
      hookTemplates: [
        'Фитнес работает не тогда, когда вы “стараетесь идеально”, а когда выстраивается система.',
        'Срывы чаще происходят не из-за слабой воли, а из-за слишком жёсткого старта.',
        'Хороший прогресс начинается с посильного плана, который можно выдержать в жизни.',
      ],
      ctaTemplates: [
        'Напишите «СТАРТ», если хотите подобрать посильный план тренировок.',
        'Сохраните пост, чтобы вернуться к нему, когда мотивация начнёт падать.',
        'Напишите в сообщения, если хотите понять, с чего начать именно вам.',
      ],
      offerTemplates: ['план старта', 'подбор тренировочного формата', 'разбор цели и режима'],
      bannedCrossNicheWords: ['карма', 'полнолуние', 'барбер', 'авто', 'ремонт квартиры'],
    },
    {
      id: 'esoterica',
      label: 'Эзотерика',
      aliases: ['эзотерика', 'esoterics', 'esoterica', 'духовные практики', 'энергия', 'интуиция'],
      keywords: ['энергия', 'интуиция', 'осознанность', 'лунные циклы', 'изобилие', 'внутреннее состояние'],
      audience: 'Люди, которым важны внутреннее состояние, интуиция, энергия и бережный взгляд на личные перемены.',
      painPoints: ['Сложно понять свои внутренние сигналы', 'Есть ощущение повторяющихся сценариев', 'Не хватает спокойных и понятных практик для внутренней опоры'],
      contentAngles: ['энергия', 'интуиция', 'духовные практики', 'знаки Вселенной', 'очищение пространства', 'аффирмации', 'лунные циклы', 'карма', 'внутреннее состояние', 'жизненный путь', 'изобилие', 'защита от негатива', 'родовые сценарии', 'духовное пробуждение', 'осознанность'],
      topicTemplates: [
        '5 знаков от Вселенной, которые вы можете не замечать',
        'Почему в жизни повторяются одни и те же уроки',
        'Что нельзя делать в полнолуние',
        'Как понять, что ваша интуиция пытается вас предупредить',
        '3 признака энергетического истощения',
        'Почему желания не исполняются, даже если вы очень стараетесь',
        'Как очистить дом от тяжелой энергии',
        'Почему вы постоянно видите одинаковые числа',
        'Что такое духовное пробуждение простыми словами',
        'Как защитить себя от чужой негативной энергии',
        'Какие вещи могут блокировать поток изобилия',
        'Почему прошлое не отпускает и как это связано с энергией',
        'Как начать слышать свою интуицию',
        'Что означает чувство дежавю с эзотерической точки зрения',
        'Почему некоторые люди появляются в нашей жизни не случайно',
        'Какие признаки указывают на внутренний дисбаланс',
        'Как подготовиться к новолунию',
        'Что делать, если чувствуете упадок энергии',
        'Как мысли влияют на состояние и события',
        'Почему важно отпускать старое перед новым этапом жизни',
        'Как понять, что пространство дома нуждается в очищении',
        'Почему после общения с некоторыми людьми вы чувствуете опустошение',
      ],
      hookTemplates: [
        'Иногда внутренние сигналы становятся тише не потому, что их нет, а потому что в жизни слишком много шума.',
        'Повторяющиеся ситуации часто указывают не на случайность, а на непройденный внутренний урок.',
        'Эзотерические практики работают лучше всего там, где есть бережность, наблюдение и опора на себя.',
      ],
      ctaTemplates: [
        'Напишите «ЭНЕРГИЯ», если хотите подобрать мягкую практику под ваше состояние.',
        'Сохраните пост, чтобы вернуться к нему в спокойный момент и перечитать знаки.',
        'Напишите в сообщения, если хотите разобраться, с чего начать путь к внутренней опоре.',
      ],
      offerTemplates: ['диагностика состояния', 'подбор мягкой практики', 'разбор повторяющегося сценария'],
      bannedCrossNicheWords: ['автосервис', 'барбер', 'ремонт квартиры', 'лидогенерация', 'контент-воронка', 'чистка лица'],
    },
  ];

  const fallback = {
    id: 'fallback',
    label: 'Универсальная ниша',
    aliases: ['fallback', 'other', 'другое'],
    keywords: ['услуги', 'клиенты', 'польза'],
    audience: 'Люди, которые выбирают услугу и хотят понять выгоду простыми словами.',
    painPoints: ['Сложно выбрать решение', 'Неясно, кому доверять', 'Хочется больше понятности и пользы'],
    contentAngles: ['практические советы', 'частые ошибки', 'понятный разбор', 'польза и результат'],
    topicTemplates: [
      '3 частые ошибки клиентов при выборе решения',
      'Как подготовиться перед обращением, чтобы получить лучший результат',
      'Какие вопросы стоит задать до старта работы',
      'Что помогает выбрать услугу без лишнего стресса',
      'Как понять, что решение действительно вам подходит',
      'Почему прозрачный процесс снижает тревогу клиента',
      'Что люди чаще всего откладывают зря',
      'Какие признаки указывают на хорошее качество услуги',
      'Как сэкономить время и избежать типичных ошибок',
      'Почему понятный следующий шаг повышает уверенность клиента',
    ],
    hookTemplates: [
      'Когда услуга объяснена простыми словами, клиенту легче принять решение.',
      'Чаще всего люди откладывают не из-за цены, а из-за неясности следующего шага.',
      'Хороший контент помогает человеку быстрее понять свою выгоду.',
    ],
    ctaTemplates: [
      'Напишите в сообщения, если хотите получить рекомендацию под свою ситуацию.',
      'Сохраните пост, чтобы вернуться к нему перед выбором услуги.',
      'Напишите, если хотите быстро понять следующий шаг без лишней теории.',
    ],
    offerTemplates: ['первичная консультация', 'разбор задачи', 'подбор решения'],
    bannedCrossNicheWords: [],
  };
  const NICHE_IMAGE_GUIDELINES = {
    smm_marketing: {
      style: 'clean editorial workspace',
      focus: 'marketing planning, content workflow, analytics on screen, business owner or marketer at work',
      mood: 'professional, modern, clear',
      avoid: ['stock handshake', 'random abstract gradients', 'empty office scene'],
    },
    cosmetology: {
      style: 'clean beauty editorial',
      focus: 'healthy skin, cosmetology cabinet, specialist hands, skincare routine details',
      mood: 'premium, soft, sterile, trustworthy',
      avoid: ['plastic doll skin', 'medical horror visuals', 'oversexualized beauty'],
    },
    barbershop: {
      style: 'masculine lifestyle portrait',
      focus: 'grooming process, haircut details, beard care, barbershop interior',
      mood: 'confident, stylish, authentic',
      avoid: ['fashion runway glamour', 'female beauty salon cues', 'cartoon barber tools'],
    },
    autoservice: {
      style: 'realistic automotive service photo',
      focus: 'car diagnostics, mechanic inspection, workshop details, under-hood service moments',
      mood: 'reliable, practical, honest',
      avoid: ['race cars', 'luxury showroom', 'toy car look', 'crash scene'],
    },
    detailing: {
      style: 'premium auto detailing visual',
      focus: 'paint protection, polished bodywork, interior care, close-up detailing process',
      mood: 'clean, premium, precise',
      avoid: ['repair garage look', 'oil and dirt focus', 'racing aesthetic'],
    },
    apartment_renovation: {
      style: 'interior renovation documentary',
      focus: 'apartment renovation stages, materials, measuring, neat work process, before/after readiness',
      mood: 'practical, trustworthy, organized',
      avoid: ['luxury palace interior', 'messy demolition chaos only', 'DIY meme look'],
    },
    psychology: {
      style: 'calm human-centered lifestyle',
      focus: 'thoughtful person, safe conversation, reflection, emotional balance, everyday life scenes',
      mood: 'warm, safe, grounded',
      avoid: ['clinical psychiatry clichés', 'esoteric symbols', 'dramatic crying close-ups'],
    },
    consulting: {
      style: 'business strategy editorial',
      focus: 'decision-making, leadership meeting, documents, planning session, process clarity',
      mood: 'strategic, premium, confident',
      avoid: ['generic corporate handshake', 'startup party vibe', 'stock presentation clichés'],
    },
    online_courses: {
      style: 'modern online learning scene',
      focus: 'expert teaching, laptop learning, lesson fragments, study notes, remote education',
      mood: 'clear, motivating, expert',
      avoid: ['school classroom for children', 'gaming streamer setup', 'random webinar stock'],
    },
    fitness: {
      style: 'realistic fitness lifestyle',
      focus: 'training process, movement, recovery, coach guidance, gym or home workout setup',
      mood: 'energetic, healthy, disciplined',
      avoid: ['extreme bodybuilding only', 'supplement ads', 'unreal body proportions'],
    },
    esoterica: {
      style: 'calm spiritual lifestyle visual',
      focus: 'inner state, meditation, moonlight, candles, gentle rituals, intuitive reflective moments',
      mood: 'mysterious, soft, thoughtful, elegant',
      avoid: ['cheap magic props', 'horror occult look', 'circus mysticism', 'neon fantasy chaos'],
    },
    fallback: {
      style: 'clean commercial editorial',
      focus: 'service, client value, real-world scene connected to the topic',
      mood: 'clear, useful, trustworthy',
      avoid: ['abstract stock filler', 'text on image', 'random unrelated objects'],
    },
  };

  function normalizeKey(value) {
    return String(value || '').trim().toLowerCase();
  }

  function normalizeCategory(category) {
    const raw = normalizeKey(category);
    if (!raw) return fallback.id;
    for (const niche of nicheList) {
      if (normalizeKey(niche.id) === raw || normalizeKey(niche.label) === raw) return niche.id;
      if ((niche.aliases || []).some((alias) => normalizeKey(alias) === raw)) return niche.id;
    }
    return fallback.id;
  }

  function getNicheTemplates(category) {
    const normalized = normalizeCategory(category);
    const niche = nicheList.find((item) => item.id === normalized) || fallback;
    return {
      ...niche,
      imageGuidelines: { ...(NICHE_IMAGE_GUIDELINES[niche.id] || NICHE_IMAGE_GUIDELINES.fallback) },
    };
  }

  function seededShuffle(items, seed = 0) {
    let localSeed = Array.from(String(seed || 0)).reduce((acc, char) => acc + char.charCodeAt(0), 17);
    const next = () => {
      localSeed = (localSeed * 1664525 + 1013904223) >>> 0;
      return localSeed / 4294967296;
    };
    return [...items].sort(() => next() - 0.5);
  }

  function getRandomTopicIdeas(category, count = 5, seed = 0) {
    const niche = getNicheTemplates(category);
    const pool = Array.isArray(niche.topicTemplates) && niche.topicTemplates.length
      ? niche.topicTemplates
      : fallback.topicTemplates;
    return seededShuffle(pool, `${niche.id}:${seed}`).slice(0, Math.max(1, Math.min(Number(count) || 5, pool.length)));
  }

  function getTopicHooks(category) {
    return [...(getNicheTemplates(category).hookTemplates || fallback.hookTemplates)];
  }

  function getCtaTemplates(category) {
    return [...(getNicheTemplates(category).ctaTemplates || fallback.ctaTemplates)];
  }

  function getOfferTemplates(category) {
    return [...(getNicheTemplates(category).offerTemplates || fallback.offerTemplates)];
  }

  function getContentAngles(category) {
    return [...(getNicheTemplates(category).contentAngles || fallback.contentAngles)];
  }

  function getFallbackTemplates() {
    return fallback;
  }

  const GENERIC_POST_CTA_POOL = [
    'Сохраните пост, чтобы вернуться к нему в нужный момент.',
    'Поделитесь с тем, кому это сейчас может быть полезно.',
    'Напишите в комментариях, если узнали свою ситуацию.',
    'Ответьте одним словом: откликается или нет?',
    'Возьмите этот пост как ориентир перед следующим шагом.',
  ];

  const POST_CONTENT_SHAPES = [
    { key: 'educational', format: 'expert_post' },
    { key: 'checklist', format: 'checklist_post' },
    { key: 'question', format: 'question_post' },
    { key: 'mini_story', format: 'story_post' },
    { key: 'practical_step', format: 'tips_post' },
    { key: 'reflection', format: 'reflect_post' },
  ];

  function normalizePlanText(value) {
    return String(value || '')
      .toLowerCase()
      .replace(/[«»"'`]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function dedupeStrings(items, fallbackItems = []) {
    const source = Array.isArray(items) && items.length ? items : fallbackItems;
    const out = [];
    const seen = new Set();
    for (const item of source || []) {
      const text = String(item || '').trim();
      const key = normalizePlanText(text);
      if (!text || !key || seen.has(key)) continue;
      seen.add(key);
      out.push(text);
    }
    return out;
  }

  function pickBalanced(sourceItems, usageMap, previousValue, seedIndex = 0, fallbackItems = []) {
    const source = dedupeStrings(sourceItems, fallbackItems);
    if (!source.length) return '';
    let minCount = Infinity;
    let candidateIndexes = [];
    source.forEach((item, idx) => {
      if (item === previousValue && source.length > 1) return;
      const used = Number(usageMap.get(item) || 0);
      if (used < minCount) {
        minCount = used;
        candidateIndexes = [idx];
      } else if (used === minCount) {
        candidateIndexes.push(idx);
      }
    });
    if (!candidateIndexes.length) {
      candidateIndexes = source.map((_, idx) => idx);
    }
    const chosenIndex = candidateIndexes[seedIndex % candidateIndexes.length];
    const chosen = source[chosenIndex] || source[0];
    usageMap.set(chosen, Number(usageMap.get(chosen) || 0) + 1);
    return chosen;
  }

  function buildPostDraft(entry, index) {
    const topic = String(entry.topic || '').trim();
    const angle = String(entry.angle || '').trim();
    const hook = String(entry.hook || topic).trim();
    const cta = String(entry.cta || '').trim();
    const shape = String(entry.contentShape || 'educational').trim();
    const finalLine = cta || 'Сохраните пост, чтобы вернуться к нему позже.';

    if (shape === 'checklist') {
      return `${hook}\n\nПроверьте себя по трём точкам: что уже работает, где чаще всего появляется сбой и какой шаг даст самый быстрый сдвиг.\n\n${angle} помогает увидеть это без лишней суеты.\n\n${finalLine}`.trim();
    }
    if (shape === 'question') {
      return `${hook}\n\nЧасто всё начинается с одного вопроса: что именно сейчас мешает получить более ровный результат?\n\n${angle} помогает посмотреть на ситуацию спокойнее и честнее.\n\n${finalLine}`.trim();
    }
    if (shape === 'mini_story') {
      return `${hook}\n\nОбычно человек замечает проблему не сразу: сначала кажется, что можно отложить, а потом та же ситуация повторяется снова.\n\n${angle} как раз про тот момент, когда становится ясно, где теряется опора.\n\n${finalLine}`.trim();
    }
    if (shape === 'practical_step') {
      return `${hook}\n\nНачните с одного простого действия уже сегодня, не пытаясь переделать всё сразу.\n\n${angle} лучше всего работает тогда, когда есть один конкретный шаг и понятный ориентир на ближайшие дни.\n\n${finalLine}`.trim();
    }
    if (shape === 'reflection') {
      return `${hook}\n\nИногда полезнее не ускоряться, а честно посмотреть, что именно повторяется из раза в раз.\n\n${angle} помогает заметить это без давления и лишнего шума.\n\n${finalLine}`.trim();
    }
    return `${hook}\n\n${angle} помогает быстрее понять, где именно теряется результат и на что стоит обратить внимание в первую очередь.\n\nОдин понятный шаг всегда работает лучше, чем перегруз из советов.\n\n${finalLine}`.trim();
  }

  function pickCycled(items, index, fallbackItems = []) {
    const source = Array.isArray(items) && items.length ? items : fallbackItems;
    if (!source.length) return '';
    return String(source[index % source.length] || '').trim();
  }

  function buildPlanEntry(category, index, contentType = 'post', planContext = null) {
    const niche = getNicheTemplates(category);
    const fallbackNiche = getFallbackTemplates();
    const topics = planContext?.topicsPool || getRandomTopicIdeas(category, Math.max(10, niche.topicTemplates?.length || 10), index);
    const hooks = planContext?.hooksPool || getTopicHooks(category);
    const ctas = planContext?.ctasPool || getCtaTemplates(category);
    const offers = planContext?.offersPool || getOfferTemplates(category);
    const angles = planContext?.anglesPool || getContentAngles(category);
    const topic = pickBalanced(
      topics,
      planContext?.topicUsage || new Map(),
      planContext?.lastTopic || '',
      index,
      fallbackNiche.topicTemplates,
    );
    const angle = pickBalanced(
      angles,
      planContext?.angleUsage || new Map(),
      planContext?.lastAngle || '',
      index + 1,
      fallbackNiche.contentAngles,
    );
    const hook = pickBalanced(
      hooks,
      planContext?.hookUsage || new Map(),
      planContext?.lastHook || '',
      index + 2,
      fallbackNiche.hookTemplates,
    );
    const cta = pickBalanced(
      ctas,
      planContext?.ctaUsage || new Map(),
      planContext?.lastCta || '',
      index + 3,
      fallbackNiche.ctaTemplates,
    );
    const offer = pickBalanced(
      offers,
      planContext?.offerUsage || new Map(),
      planContext?.lastOffer || '',
      index + 4,
      fallbackNiche.offerTemplates,
    );
    const stage = index % 4;
    const objectiveMap = ['awareness', 'engagement', 'lead', 'trust'];
    const shapeSource = Array.isArray(planContext?.shapePool) && planContext.shapePool.length
      ? planContext.shapePool
      : POST_CONTENT_SHAPES;
    const shapeEntry = contentType === 'video'
      ? { key: index % 2 === 0 ? 'short_video' : 'talking_head_video', format: index % 2 === 0 ? 'short_video' : 'talking_head_video' }
      : shapeSource[index % shapeSource.length];
    const entry = {
      day: index + 1,
      nicheId: niche.id,
      nicheLabel: niche.label,
      contentType,
      contentFormat: shapeEntry.format,
      contentShape: shapeEntry.key,
      objective: objectiveMap[stage],
      angle,
      topic,
      hook,
      cta,
      offer,
      keywords: [...(niche.keywords || fallbackNiche.keywords || [])],
    };
    if (planContext) {
      planContext.lastTopic = topic;
      planContext.lastAngle = angle;
      planContext.lastHook = hook;
      planContext.lastCta = cta;
      planContext.lastOffer = offer;
    }
    if (contentType === 'post') {
      const draft = buildPostDraft(entry, index);
      entry.captionText = draft;
      entry.postText = draft;
      entry.caption = draft;
    }
    return entry;
  }

  function getContentPlan(category, days = 7, contentType = 'post') {
    const total = Math.max(1, Math.min(30, Number(days) || 7));
    const niche = getNicheTemplates(category);
    const fallbackNiche = getFallbackTemplates();
    const planContext = {
      topicsPool: seededShuffle(
        dedupeStrings(niche.topicTemplates, fallbackNiche.topicTemplates),
        `${niche.id}:${contentType}:topics:${total}`,
      ),
      hooksPool: seededShuffle(
        dedupeStrings(niche.hookTemplates, fallbackNiche.hookTemplates),
        `${niche.id}:${contentType}:hooks:${total}`,
      ),
      anglesPool: seededShuffle(
        dedupeStrings(niche.contentAngles, fallbackNiche.contentAngles),
        `${niche.id}:${contentType}:angles:${total}`,
      ),
      ctasPool: seededShuffle(
        dedupeStrings([...(niche.ctaTemplates || []), ...GENERIC_POST_CTA_POOL], [...fallbackNiche.ctaTemplates, ...GENERIC_POST_CTA_POOL]),
        `${niche.id}:${contentType}:ctas:${total}`,
      ),
      offersPool: seededShuffle(
        dedupeStrings(niche.offerTemplates, fallbackNiche.offerTemplates),
        `${niche.id}:${contentType}:offers:${total}`,
      ),
      shapePool: seededShuffle(POST_CONTENT_SHAPES, `${niche.id}:${contentType}:shapes:${total}`),
      topicUsage: new Map(),
      hookUsage: new Map(),
      angleUsage: new Map(),
      ctaUsage: new Map(),
      offerUsage: new Map(),
      lastTopic: '',
      lastHook: '',
      lastAngle: '',
      lastCta: '',
      lastOffer: '',
    };
    return Array.from({ length: total }, (_, idx) => buildPlanEntry(category, idx, contentType, planContext));
  }

  function get7DayContentPlan(category, contentType = 'post') {
    return getContentPlan(category, 7, contentType);
  }

  function get30DayContentPlan(category, contentType = 'post') {
    return getContentPlan(category, 30, contentType);
  }

  function getPostSeries(category, count = 5) {
    const total = Math.max(1, Math.min(15, Number(count) || 5));
    return Array.from({ length: total }, (_, idx) => ({
      seriesIndex: idx + 1,
      ...buildPlanEntry(category, idx, 'post'),
    }));
  }

  function getVideoSeries(category, count = 5) {
    const total = Math.max(1, Math.min(15, Number(count) || 5));
    return Array.from({ length: total }, (_, idx) => ({
      seriesIndex: idx + 1,
      ...buildPlanEntry(category, idx, 'video'),
    }));
  }

  function getNicheOptions() {
    return nicheList.map((item) => ({ value: item.id, label: item.label }));
  }

  function buildNicheAiContext(category) {
    const niche = getNicheTemplates(category);
    return {
      id: niche.id,
      label: niche.label,
      keywords: [...(niche.keywords || [])],
      audience: niche.audience,
      painPoints: [...(niche.painPoints || [])],
      contentAngles: [...(niche.contentAngles || [])],
      topicTemplates: [...(niche.topicTemplates || [])],
      hookTemplates: [...(niche.hookTemplates || [])],
      ctaTemplates: [...(niche.ctaTemplates || [])],
      offerTemplates: [...(niche.offerTemplates || [])],
      imageGuidelines: { ...(niche.imageGuidelines || NICHE_IMAGE_GUIDELINES.fallback) },
      bannedCrossNicheWords: [...(niche.bannedCrossNicheWords || [])],
      contentPlan7Days: get7DayContentPlan(niche.id, 'post'),
      contentPlan30Days: get30DayContentPlan(niche.id, 'post'),
      postSeriesTemplates: getPostSeries(niche.id, 7),
      videoSeriesTemplates: getVideoSeries(niche.id, 7),
    };
  }

  window.AutoSocialNiches = {
    DEFAULT_NICHE_ID: nicheList[0].id,
    NICHE_TEMPLATE_LIBRARY: nicheList,
    normalizeCategory,
    getNicheTemplates,
    getRandomTopicIdeas,
    getTopicHooks,
    getCtaTemplates,
    getOfferTemplates,
    getContentAngles,
    getContentPlan,
    get7DayContentPlan,
    get30DayContentPlan,
    getPostSeries,
    getVideoSeries,
    getFallbackTemplates,
    getNicheOptions,
    buildNicheAiContext,
  };
})();
