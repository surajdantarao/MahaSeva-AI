import type { Language } from './types';

export const t: Record<Language, {
  siteTitle: string;
  siteSubtitle: string;
  navHome: string;
  navSchemes: string;
  navCategories: string;
  navAssistant: string;
  navAbout: string;
  navDepartments: string;
  navAdmin: string;
  navAdminLoggedIn: string;
  heroBadge: string;
  heroHeading: string;
  heroDesc: string;
  searchPlaceholder: string;
  btnSearch: string;
  btnAskAI: string;
  statTotal: string;
  statVerified: string;
  statDepartments: string;
  catAll: string;
  catFarmers: string;
  catWomen: string;
  catSocial: string;
  catRural: string;
  catUrban: string;
  quickQuestionsHeading: string;
  q1: string;
  q2: string;
  q3: string;
  filterAll: string;
  filterVerifiedOnly: string;
  filterPendingReview: string;
  filterDeptLabel: string;
  filterAllDepts: string;
  filterDeadlineLabel: string;
  filterDeadlineAll: string;
  filterDeadlineOpen: string;
  filterDeadlineClosing: string;
  filterDeadlineUpcoming: string;
  filterDeadlineNoDeadline: string;
  filterDeadlineClosed: string;
  sortByLabel: string;
  sortNewest: string;
  sortAlpha: string;
  sortDeadline: string;
  badgeVerified: string;
  badgePending: string;
  badgeNeedsUpdate: string;
  badgeLikelyState: string;
  badgeCentral: string;
  btnViewDetails: string;
  btnOfficialLink: string;
  btnApplyNow: string;
  btnAskAboutScheme: string;
  noSchemesFound: string;
  noSchemesHelp: string;
  cardDept: string;
  cardBenefits: string;
  cardEligibility: string;
  cardDeadline: string;
  cardStatus: string;
  noDeadlineNotice: string;
  detailTitle: string;
  detailOverview: string;
  detailEligibilityBenefits: string;
  detailApplication: string;
  detailProvenance: string;
  detailDesc: string;
  detailDocsRequired: string;
  detailProcess: string;
  detailPdfLinks: string;
  detailLastRetrieved: string;
  detailLastVerified: string;
  detailReviewer: string;
  detailSourceUrl: string;
  detailWindowsTitle: string;
  aiHeading: string;
  aiDesc: string;
  aiPrivacyNotice: string;
  aiInputPlaceholder: string;
  btnSend: string;
  aiThinking: string;
  aiSourcesTitle: string;
  aiDisclaimerTitle: string;
  footerDisclaimer: string;
  footerLinks: string;
  footerPrivacy: string;
  // Sections
  sectionOpenNow: string;
  sectionClosingSoon: string;
  sectionUpcoming: string;
  sectionNoDeadline: string;
  sectionRecentlyAnnounced: string;
  sectionRecentlyUpdated: string;
  sectionClosed: string;
  // Contextual Chat
  chatModalTitle: string;
  chatModalSub: string;
  chatModalClose: string;
  chatModalInput: string;
  chatNoticeNoPersist: string;
  chipEligibility: string;
  chipDocuments: string;
  chipHowToApply: string;
  chipDeadline: string;
  // Admin Tabs
  adminTabReview: string;
  adminTabChanges: string;
  adminTabAudit: string;
  adminTabSources: string;
  adminRunScanBtn: string;
  adminSchedulerLive: string;
  btnNewChat: string;
  aboutHeading: string;
  categoriesHeading: string;
  officialSourcesTitle: string;
  officialSourcesDesc: string;
}> = {
  en: {
    siteTitle: 'MahaSeva AI',
    siteSubtitle: 'Government of Maharashtra Scheme Discovery & Citizen Assistance',
    navHome: 'Home',
    navSchemes: 'Schemes',
    navCategories: 'Categories',
    navAssistant: 'Assistant',
    navAbout: 'About & Sources',
    navDepartments: 'Departments',
    navAdmin: 'Officer Portal',
    navAdminLoggedIn: 'Dashboard',
    heroBadge: 'Official Maharashtra Citizen Platform',
    heroHeading: 'Discover Government Schemes You Are Eligible For',
    heroDesc:
      'Search verified Maharashtra state schemes, track active application deadlines, understand eligibility rules, and get direct links to official government portals.',
    searchPlaceholder: 'Search by scheme name, keyword (e.g. farmer subsidy, scholarship, housing)...',
    btnSearch: 'Search Schemes',
    btnAskAI: 'Ask AI Assistant',
    statTotal: 'Total Catalogued',
    statVerified: 'Verified State Schemes',
    statDepartments: 'Official Departments',
    catAll: 'All Categories',
    catFarmers: 'Farmers & Agriculture',
    catWomen: 'Women & Child',
    catSocial: 'Social Justice & Welfare',
    catRural: 'Rural Development',
    catUrban: 'Urban Development',
    quickQuestionsHeading: 'Frequently Asked Questions',
    q1: 'Which Maharashtra government schemes are open for applications now?',
    q2: 'Which schemes are closing soon this month?',
    q3: 'Show me schemes that have no application deadline published.',
    filterAll: 'All Statuses',
    filterVerifiedOnly: 'Verified State Schemes Only',
    filterPendingReview: 'Candidates Under Review',
    filterDeptLabel: 'Department:',
    filterAllDepts: 'All Departments',
    filterDeadlineLabel: 'Application Window:',
    filterDeadlineAll: 'All Window States',
    filterDeadlineOpen: 'Applications Open Now',
    filterDeadlineClosing: 'Closing Soon',
    filterDeadlineUpcoming: 'Upcoming Schemes',
    filterDeadlineNoDeadline: 'No Deadline Published',
    filterDeadlineClosed: 'Closed Application Windows',
    sortByLabel: 'Sort By:',
    sortNewest: 'Newest First',
    sortAlpha: 'Alphabetical',
    sortDeadline: 'Nearest Deadline',
    badgeVerified: 'Verified State Scheme',
    badgePending: 'Candidate Under Review',
    badgeNeedsUpdate: 'Reviewing Recent Update',
    badgeLikelyState: 'State Program',
    badgeCentral: 'Central / Joint Review',
    btnViewDetails: 'View Details',
    btnOfficialLink: 'Official Source',
    btnApplyNow: 'Apply on Official Portal',
    btnAskAboutScheme: 'Ask AI About This Scheme',
    noSchemesFound: 'No Schemes Match Your Search Criteria',
    noSchemesHelp: 'Try broadening your search term or resetting the filters.',
    cardDept: 'Department',
    cardBenefits: 'Benefits',
    cardEligibility: 'Eligibility',
    cardDeadline: 'Application Deadline',
    cardStatus: 'Status',
    noDeadlineNotice: 'No application deadline published by the available official sources.',
    detailTitle: 'Scheme Information',
    detailOverview: 'Overview',
    detailEligibilityBenefits: 'Eligibility & Benefits',
    detailApplication: 'Application & Official Links',
    detailProvenance: 'Source & Verification Provenance',
    detailDesc: 'Description',
    detailDocsRequired: 'Required Documents',
    detailProcess: 'Application Procedure',
    detailPdfLinks: 'Official Notifications & PDFs',
    detailLastRetrieved: 'Last Retrieved',
    detailLastVerified: 'Last Reviewed',
    detailReviewer: 'Reviewed By',
    detailSourceUrl: 'Official Source Portal',
    detailWindowsTitle: 'Application Rounds & History',
    aiHeading: 'Bilingual Citizen AI Assistant',
    aiDesc:
      'Ask any question regarding Maharashtra state schemes in English, मराठी (Marathi), or Romanized Marathi. All answers cite official government sources.',
    aiPrivacyNotice:
      'Privacy Shield: MahaSeva AI never asks for or stores Aadhaar or bank account numbers.',
    aiInputPlaceholder: 'Ask a question in English or मराठी (e.g. "Which farmer schemes are open now?")...',
    btnSend: 'Send',
    aiThinking: 'Retrieving official government sources...',
    aiSourcesTitle: 'Verified Government Sources Cited',
    aiDisclaimerTitle: 'Important Official Notice',
    footerDisclaimer:
      'MahaSeva AI is an automated discovery and citizen assistance platform. All schemes and benefits are governed by official Government Resolutions (GR).',
    footerLinks: 'Official Portals: Maharashtra State Portal | MahaDBT Portal | Aaple Sarkar',
    footerPrivacy: 'Zero Personal Data Stored | Official Source Citations Guaranteed',
    // Sections
    sectionOpenNow: 'Applications Open Now',
    sectionClosingSoon: 'Closing Soon',
    sectionUpcoming: 'Upcoming Schemes',
    sectionNoDeadline: 'No Published Deadline',
    sectionRecentlyAnnounced: 'Recently Announced Schemes',
    sectionRecentlyUpdated: 'Recently Updated Schemes',
    sectionClosed: 'Closed Application Windows',
    // Contextual Chat
    chatModalTitle: 'Contextual AI Assistance',
    chatModalSub: 'Asking specifically about this scheme. Verified dates and status provided.',
    chatModalClose: 'Close Session',
    chatModalInput: 'Ask about this scheme (e.g. "When is the last date?", "What are the documents?")...',
    chatNoticeNoPersist: 'Temporary session. Cleared upon closing or page navigation.',
    chipEligibility: '📋 Check Eligibility',
    chipDocuments: '📄 Required Documents',
    chipHowToApply: '🚀 How to Apply',
    chipDeadline: '📅 Application Deadline',
    // Admin Tabs
    adminTabReview: 'Candidate Review Queue',
    adminTabChanges: 'Detected Changes Queue',
    adminTabAudit: 'Verification Audit Logs',
    adminTabSources: 'Source Registry & Health',
    adminRunScanBtn: 'Trigger Source Monitoring Scan',
    adminSchedulerLive: 'Automated Monitoring Scheduler: Active',
    btnNewChat: 'New Chat (Reset)',
    aboutHeading: 'About MahaSeva AI & Official Sources',
    categoriesHeading: 'Maharashtra Government Scheme Categories',
    officialSourcesTitle: 'Validated Official Maharashtra Sources Registry',
    officialSourcesDesc: 'Every scheme in MahaSeva AI is monitored from verified Maharashtra Government portals, departments, and gazettes.',
  },
  mr: {
    siteTitle: 'महासेवा एआय',
    siteSubtitle: 'महाराष्ट्र शासन योजना शोध व नागरिक साहाय्यक मंच',
    navHome: 'मुख्यपृष्ठ',
    navSchemes: 'योजना',
    navCategories: 'वर्गवारी',
    navAssistant: 'एआय साहाय्यक',
    navAbout: 'माहिती व स्रोत',
    navDepartments: 'शासकीय विभाग',
    navAdmin: 'अधिकारी दालन',
    navAdminLoggedIn: 'डॅशबोर्ड',
    heroBadge: 'अधिकृत महाराष्ट्र नागरिक साहाय्यक प्लॅटफॉर्म',
    heroHeading: 'आपल्यासाठी पात्र असणाऱ्या शासकीय योजना शोधा',
    heroDesc:
      'महाराष्ट्र शासनाच्या पडताळणी झालेल्या योजना, चालू अर्ज मुदती, आवश्यक पात्रता व कागदपत्रे जाणून घ्या आणि थेट अधिकृत पोर्टलवरून अर्ज करा.',
    searchPlaceholder: 'योजनेचे नाव किंवा शब्द शोधा (उदा. शेतकरी अनुदान, शिष्यवृत्ती, घरकुल)...',
    btnSearch: 'योजना शोधा',
    btnAskAI: 'एआय साहाय्यकाला विचारा',
    statTotal: 'एकूण नोंदणीकृत योजना',
    statVerified: 'पडताळणी झालेल्या राज्य योजना',
    statDepartments: 'शासकीय विभाग',
    catAll: 'सर्व विभाग व वर्गवारी',
    catFarmers: 'शेतकरी व कृषी योजना',
    catWomen: 'महिला व बाल विकास',
    catSocial: 'सामाजिक न्याय व विशेष सहाय्य',
    catRural: 'ग्राम विकास',
    catUrban: 'नगर विकास',
    quickQuestionsHeading: 'नेहमी विचारले जाणारे प्रश्न',
    q1: 'महाराष्ट्रात सध्या कोणत्या योजनांचे अर्ज सुरू आहेत?',
    q2: 'या महिन्यात कोणत्या योजनांची मुदत संपत आहे?',
    q3: 'ज्या योजनांना अंतिम तारीख नाही त्या दाखवा.',
    filterAll: 'सर्व स्थिती',
    filterVerifiedOnly: 'केवळ पडताळणी झालेल्या राज्य योजना',
    filterPendingReview: 'पडताळणी प्रलंबित योजना',
    filterDeptLabel: 'शासकीय विभाग:',
    filterAllDepts: 'सर्व विभाग',
    filterDeadlineLabel: 'अर्जाची स्थिती:',
    filterDeadlineAll: 'सर्व अर्ज स्थिती',
    filterDeadlineOpen: 'अर्ज आता सुरू आहेत',
    filterDeadlineClosing: 'लवकरच मुदत संपत आहे',
    filterDeadlineUpcoming: 'लवकरच सुरू होणार',
    filterDeadlineNoDeadline: 'अंतिम तारीख नमूद नाही',
    filterDeadlineClosed: 'अर्ज मुदत संपली',
    sortByLabel: 'क्रमवारी:',
    sortNewest: 'नवीनतम आधी',
    sortAlpha: 'अक्षरक्रमानुसार',
    sortDeadline: 'जवळची मुदत आधी',
    badgeVerified: 'पडताळणी झालेली राज्य योजना',
    badgePending: 'पडताळणी प्रलंबित',
    badgeNeedsUpdate: 'नवीन माहिती पडताळणी बाकी',
    badgeLikelyState: 'राज्य योजना',
    badgeCentral: 'केंद्र / संयुक्त योजना',
    btnViewDetails: 'तपशील पहा',
    btnOfficialLink: 'अधिकृत माहिती स्रोत',
    btnApplyNow: 'अधिकृत पोर्टलवर अर्ज करा',
    btnAskAboutScheme: 'या योजनेबद्दल एआयला विचारा',
    noSchemesFound: 'आपल्या निकषांशी जुळणारी एकही योजना आढळली नाही',
    noSchemesHelp: 'कृपया इतर शब्द वापरून पहा किंवा फिल्टर पूर्ववत करा.',
    cardDept: 'विभाग',
    cardBenefits: 'योजनेचा लाभ',
    cardEligibility: 'पात्रता निकष',
    cardDeadline: 'अंतिम मुदत',
    cardStatus: 'अर्जाची स्थिती',
    noDeadlineNotice: 'उपलब्ध अधिकृत स्रोतांमध्ये अर्जाची अंतिम तारीख नमूद केलेली नाही.',
    detailTitle: 'योजनेची सविस्तर माहिती',
    detailOverview: 'थोडक्यात माहिती',
    detailEligibilityBenefits: 'पात्रता व लाभ',
    detailApplication: 'अर्ज प्रक्रिया व अधिकृत लिंक्स',
    detailProvenance: 'माहितीचा स्रोत व पडताळणी',
    detailDesc: 'वर्णन',
    detailDocsRequired: 'आवश्यक कागदपत्रे',
    detailProcess: 'अर्जाची कार्यपद्धती',
    detailPdfLinks: 'अधिकृत शासन निर्णय (GR) व परिपत्रके',
    detailLastRetrieved: 'माहिती संकलित तारीख',
    detailLastVerified: 'शेवटचे पुनरावलोकन',
    detailReviewer: 'पडताळणी अधिकारी',
    detailSourceUrl: 'अधिकृत संकेतस्थळ',
    detailWindowsTitle: 'अर्ज फेऱ्या व मुदतीचा इतिहास',
    aiHeading: 'द्विभाषिक नागरिक एआय साहाय्यक',
    aiDesc:
      'महाराष्ट्र शासनाच्या योजनांबद्दल मराठी किंवा इंग्रजीत कोणताही प्रश्न विचारा. सर्व उत्तरे अधिकृत सरकारी स्रोतांवर आधारलेली असतात.',
    aiPrivacyNotice:
      'गोपनीयता हमी: महासेवा एआय कधीही आपला आधार किंवा बँक खाते क्रमांक मागत नाही.',
    aiInputPlaceholder: 'मराठी किंवा इंग्रजीत प्रश्न विचारा (उदा. "शेतकऱ्यांसाठी चालू योजना कोणत्या?")...',
    btnSend: 'पाठवा',
    aiThinking: 'अधिकृत सरकारी माहिती शोधत आहे...',
    aiSourcesTitle: 'वापरलेले अधिकृत शासकीय स्रोत',
    aiDisclaimerTitle: 'महत्त्वाची शासकीय सूचना',
    footerDisclaimer:
      'महासेवा एआय हे योजना शोध व नागरिक साहाय्यक व्यासपीठ आहे. योजनांचे अंतिम नियम संबंधित विभागाच्या शासन निर्णयावर (GR) अवलंबून असतात.',
    footerLinks: 'अधिकृत संकेतस्थळे: महाराष्ट्र शासन पोर्टल | महाडीबीटी पोर्टल | आपले सरकार',
    footerPrivacy: 'कोणताही वैयक्तिक डेटा साठवला जात नाही | १००% अधिकृत स्रोत हमी',
    // Sections
    sectionOpenNow: 'अर्ज आता सुरू आहेत',
    sectionClosingSoon: 'लवकरच मुदत संपत आहे',
    sectionUpcoming: 'लवकरच सुरू होणाऱ्या योजना',
    sectionNoDeadline: 'अंतिम तारीख नमूद नसलेल्या योजना',
    sectionRecentlyAnnounced: 'नुकत्याच जाहीर झालेल्या योजना',
    sectionRecentlyUpdated: 'नुकतीच माहिती अद्ययावत झालेल्या योजना',
    sectionClosed: 'अर्ज मुदत संपलेल्या योजना',
    // Contextual Chat
    chatModalTitle: 'योजना-विशिष्ट एआय साहाय्यक',
    chatModalSub: 'केवळ या योजनेबद्दल विचारलेले प्रश्न. पडताळणी झालेली अचूक तारीख व स्थिती.',
    chatModalClose: 'संवाद बंद करा',
    chatModalInput: 'या योजनेबद्दल विचारा (उदा. "शेवटची तारीख कधी आहे?", "कागदपत्रे कोणती लागतात?")...',
    chatNoticeNoPersist: 'हा तात्पुरता संवाद आहे. बंद केल्यावर नष्ट होईल.',
    chipEligibility: '📋 पात्रता तपासा',
    chipDocuments: '📄 आवश्यक कागदपत्रे',
    chipHowToApply: '🚀 अर्ज कसा करावा',
    chipDeadline: '📅 अंतिम मुदत',
    // Admin Tabs
    adminTabReview: 'उमेदवार पडताळणी रांग',
    adminTabChanges: 'बदल पडताळणी रांग',
    adminTabAudit: 'पडताळणी इतिहास (ऑडिट)',
    adminTabSources: 'स्रोतांची नोंदणी व स्थिती',
    adminRunScanBtn: 'स्रोत तपासणी त्वरित सुरू करा',
    adminSchedulerLive: 'स्वयंचलित स्रोत मॉनिटरिंग: कार्यरत',
    btnNewChat: 'नवीन संवाद (रिसेट)',
    aboutHeading: 'महासेवा एआय बद्दल व अधिकृत स्रोत',
    categoriesHeading: 'महाराष्ट्र शासन योजना वर्गवारी',
    officialSourcesTitle: 'पडताळणी झालेले अधिकृत शासकीय स्रोत नोंदणी',
    officialSourcesDesc: 'महासेवा एआय मधील प्रत्येक योजना अधिकृत महाराष्ट्र शासन संकेतस्थळे, विभाग आणि शासन निर्णयांवरून (GR) पडताळली जाते.',
  },
};
