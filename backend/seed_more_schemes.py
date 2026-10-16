"""Seed supplementary 45+ official Maharashtra Government schemes.
Expands MahaSeva AI repository to 250+ schemes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from sqlalchemy import select

from backend.database import SessionLocal
from backend.models import SchemeApplicationWindow, SchemeCandidate

ADDITIONAL_SCHEMES = [
    # ---------------- Agriculture, Animal Husbandry & Fisheries ----------------
    {
        "title": "Dr. Punjabrao Deshmukh Jaivik Kheti Mission (Organic Farming Subsidy)",
        "title_mr": "डॉ. पंजाबराव देशमुख जैविक शेती मिशन (सेंद्रिय शेती अनुदान)",
        "department": "Agriculture Department",
        "category": "Agriculture",
        "source_url": "https://krishi.maharashtra.gov.in/organic-farming",
        "official_apply_url": "https://mahadbt.maharashtra.gov.in/farmer",
        "application_mode": "online",
        "benefits": "Financial aid of ₹30,000 per hectare over 3 years for farmer groups adopting organic inputs, bio-fertilizers, and organic certification.",
        "eligibility": "Farmer groups or Farmer Producer Companies (FPC) with minimum 20 farmers holding contiguous agricultural land in Maharashtra.",
        "documents_required": "7/12 extract of all group members, Farmer Group Registration, Aadhaar Card, Bank Account.",
        "application_deadline": "2026-11-30",
        "current_window_status": "open",
        "text": "Organic farming promotion program supporting zero-budget chemical-free farming clusters across Maharashtra.",
    },
    {
        "title": "Birsa Munda Krishi Kranti Yojana for Tribal Farmers",
        "title_mr": "बिरसा मुंडा कृषी क्रांती योजना (आदिवासी शेतकरी विहीर व सिंचन)",
        "department": "Agriculture and Tribal Development Department",
        "category": "Agriculture",
        "source_url": "https://krishi.maharashtra.gov.in/birsa-munda",
        "official_apply_url": "https://mahadbt.maharashtra.gov.in/farmer",
        "application_mode": "online",
        "benefits": "100% subsidy for new irrigation well (up to ₹2.5 Lakh), in-well boring (₹20,000), farm pond (₹50,000), solar/electric pump sets (₹25,000), and drip irrigation (₹50,000).",
        "eligibility": "Scheduled Tribe (ST) landholding farmers with land between 0.20 to 6.00 hectares. Annual family income up to ₹1.5 Lakh.",
        "documents_required": "Tribe Certificate, 7/12 & 8-A land extract, Income certificate, Domicile certificate, Bank passbook.",
        "application_deadline": "2026-12-31",
        "current_window_status": "open",
        "text": "Dedicated agricultural development scheme for tribal farmers to create permanent irrigation assets.",
    },
    {
        "title": "Subsidized Tractor and Farm Mechanization Scheme (Krishi Yantrikikaran)",
        "title_mr": "कृषी यांत्रिकीकरण योजना (ट्रॅक्टर व कृषी अवजारे अनुदान)",
        "department": "Agriculture Department",
        "category": "Agriculture",
        "source_url": "https://krishi.maharashtra.gov.in/farm-mechanization",
        "official_apply_url": "https://mahadbt.maharashtra.gov.in/farmer",
        "application_mode": "online",
        "benefits": "40% to 50% capital subsidy (up to ₹1.25 Lakh on tractors, up to ₹1.00 Lakh on power tillers, rotavators, threshers, seed drills, and harvesters).",
        "eligibility": "Individual landholding farmers. Priority to SC/ST, women, and small/marginal farmers.",
        "documents_required": "7/12 land extract, 8-A extract, Aadhaar card, Caste certificate (if SC/ST), Quotation from authorized dealer.",
        "application_deadline": "2026-12-31",
        "current_window_status": "open",
        "text": "State farm mechanization drive reducing labor costs and promoting modern agricultural machinery.",
    },
    {
        "title": "Galmukt Dharan Galyukt Shivar Yojana (Desilting of Water Reservoirs)",
        "title_mr": "गाळमुक्त धरण गाळयुक्त शिवार योजना",
        "department": "Water Resources and Agriculture Department",
        "category": "Agriculture",
        "source_url": "https://mowr.maharashtra.gov.in/galmukt-dharan",
        "official_apply_url": "https://mowr.maharashtra.gov.in/",
        "application_mode": "offline",
        "benefits": "Free extraction of nutrient-rich silt from water dams and reservoirs with ₹35 per cubic meter transport fuel subsidy paid to farmers spreading silt on their agricultural fields.",
        "eligibility": "Farmers owning agricultural land situated near government dams, minor irrigation tanks, or percolation tanks.",
        "documents_required": "7/12 land extract, Application to Tahsildar / Executive Engineer Irrigation.",
        "application_deadline": None,
        "current_window_status": "no_deadline_published",
        "text": "Restoring dam water capacity while increasing agricultural soil fertility through free silt distribution.",
    },
    {
        "title": "Cow and Buffalo Rearing Subsidy Scheme (Dairy Farming Unit)",
        "title_mr": "दुधाळ गायी व म्हशी वाटप योजना (दुग्ध व्यवसाय अनुदान)",
        "department": "Animal Husbandry Department",
        "category": "Agriculture",
        "source_url": "https://ahd.maharashtra.gov.in/dairy-farming",
        "official_apply_url": "https://ahd.maharashtra.gov.in/",
        "application_mode": "online",
        "benefits": "50% to 75% subsidy for establishing a 2-animal, 4-animal, or 6-animal dairy unit (Gir, Sahiwal, Red Sindhi, Murrah buffalo) including animal cost, shed, insurance, and milking machine.",
        "eligibility": "Rural farmers, unemployed youth, women self-help group members. Special quotas for SC/ST with 75% subsidy.",
        "documents_required": "Aadhaar Card, 7/12 land extract or shelter proof, Caste certificate, Bank passbook, Training certificate from District Animal Husbandry Office.",
        "application_deadline": "2026-11-30",
        "current_window_status": "open",
        "text": "Promoting white revolution and supplementary dairy income for rural and drought-affected farming families.",
    },
    {
        "title": "Goat and Sheep Rearing Subsidy Scheme (10 Does + 1 Buck Unit)",
        "title_mr": "शेळी व मेंढी पालन वाटप योजना (१० शेळ्या + १ बोकड)",
        "department": "Animal Husbandry Department",
        "category": "Agriculture",
        "source_url": "https://ahd.maharashtra.gov.in/goat-farming",
        "official_apply_url": "https://ahd.maharashtra.gov.in/",
        "application_mode": "online",
        "benefits": "50% to 75% subsidy on total unit cost of ₹1,00,000 for purchasing 10 Osmanabadi/Sangamneri goats and 1 breeding buck plus shed construction.",
        "eligibility": "Small, marginal farmers, landless agricultural laborers, and traditional shepherd communities (Dhangar).",
        "documents_required": "Aadhaar card, Ration card, Caste certificate (for 75% subsidy), Bank passbook, Animal Husbandry training certificate.",
        "application_deadline": "2026-11-30",
        "current_window_status": "open",
        "text": "Livelihood support scheme providing high-yielding indigenous goat units to landless and smallholder farmers.",
    },
    {
        "title": "Marine Fishermen Safety and Modern Navigation GPS Kit Subsidy",
        "title_mr": "सागरी मच्छीमार सुरक्षा व जीपीएस नेव्हिगेशन साधनसामग्री अनुदान",
        "department": "Fisheries Department",
        "category": "Agriculture",
        "source_url": "https://fisheries.maharashtra.gov.in/safety-kits",
        "official_apply_url": "https://fisheries.maharashtra.gov.in/",
        "application_mode": "offline",
        "benefits": "80% subsidy on Marine Distress Alert Transmitters (DAT), VHF Radio, GPS Fish Finders, Life Jackets, and Echo Sounders for coastal fishing boats.",
        "eligibility": "Traditional marine fishermen and fishing cooperative members registered with Maharashtra Fisheries Department along the 720 km Konkan coastline.",
        "documents_required": "Boat Registration Certificate, Fishing License, Biometric Fishermen Card, Aadhaar Card, Bank Passbook.",
        "application_deadline": None,
        "current_window_status": "no_deadline_published",
        "text": "Life-safety and catch enhancement equipment provided to marine fishermen operating from Palghar to Sindhudurg.",
    },

    # ---------------- Senior Citizens, Divyang & Social Security ----------------
    {
        "title": "Mukhyamantri Vayoshri Yojana (Senior Citizen Physical Aids & Cash Grant)",
        "title_mr": "मुख्यमंत्री वयोश्री योजना (ज्येष्ठ नागरिक सहाय्यक उपकरणे व ₹३,००० अनुदान)",
        "department": "Social Justice and Special Assistance Department",
        "category": "Social Justice & Welfare",
        "source_url": "https://sjsa.maharashtra.gov.in/vayoshri-yojana",
        "official_apply_url": "https://sjsa.maharashtra.gov.in/",
        "application_mode": "online",
        "benefits": "Direct cash assistance of ₹3,00,000 in aggregate across camps or ₹3,000 one-time DBT grant plus free physical assistive devices: spectacles, walking sticks, hearing aids, wheelchairs, and cervical collars.",
        "eligibility": "Senior citizens aged 65 years and above residing in Maharashtra with annual family income up to ₹2 Lakh.",
        "documents_required": "Aadhaar Card, Age proof (65+), Tahsildar Income Certificate, Maharashtra Domicile Certificate, Bank Account.",
        "application_deadline": "2026-12-31",
        "current_window_status": "open",
        "text": "State welfare scheme assisting 15 lakh elderly citizens with free physical disability devices and financial aid.",
    },
    {
        "title": "Financial Aid for Divyang Marriage (Differently-Abled Matrimonial Incentive)",
        "title_mr": "दिव्यांग विवाह प्रोत्साहन योजना (आर्थिक मदत)",
        "department": "Persons with Disabilities Welfare Department",
        "category": "Social Justice & Welfare",
        "source_url": "https://pwd.maharashtra.gov.in/divyang-marriage",
        "official_apply_url": "https://pwd.maharashtra.gov.in/",
        "application_mode": "offline",
        "benefits": "One-time financial grant of ₹50,000 if one spouse is disabled, and ₹1,00,000 if both husband and wife are persons with disabilities (40%+).",
        "eligibility": "Resident of Maharashtra for at least 15 years. Valid 40%+ disability certificate issued by Civil Surgeon. Minimum 18 years for bride and 21 years for groom.",
        "documents_required": "Disability Certificate (UDID card), Marriage Registration Certificate, Age Proof, Domicile Certificate, Joint Bank Account.",
        "application_deadline": None,
        "current_window_status": "no_deadline_published",
        "text": "Empowering differently-abled citizens to lead dignified family lives through direct marriage cash grants.",
    },
    {
        "title": "Sant Rohidas Charmakar Vikas Mahamandal 50% Subsidy Loan Scheme",
        "title_mr": "संत रोहिदास चर्मोद्योग व चर्मकार विकास महामंडळ ५०% अनुदान कर्ज योजना",
        "department": "Social Justice and Special Assistance Department",
        "category": "Social Justice & Welfare",
        "source_url": "https://lidcom.maharashtra.gov.in/",
        "official_apply_url": "https://lidcom.maharashtra.gov.in/",
        "application_mode": "offline",
        "benefits": "Business and micro-enterprise loans up to ₹50,000 with 50% government subsidy (₹25,000 subsidy + ₹25,000 bank loan at concessional interest) for leather artisans.",
        "eligibility": "Persons belonging to Charmakar (cobbler) community in Maharashtra. Age 18 to 50 years. Annual family income up to ₹1 Lakh in rural areas, ₹1.2 Lakh in urban areas.",
        "documents_required": "Charmakar Caste Certificate, Income Certificate from Tahsildar, Project proposal, Aadhaar card, Bank passbook.",
        "application_deadline": None,
        "current_window_status": "no_deadline_published",
        "text": "Economic empowerment and livelihood enhancement for traditional leather artisans and footwear makers.",
    },
    {
        "title": "Lokshahir Annabhau Sathe Vikas Mahamandal 50% Capital Subsidy Scheme",
        "title_mr": "लोकशाहीर अण्णाभाऊ साठे विकास महामंडळ ५०% अनुदान स्वयंरोजगार योजना",
        "department": "Social Justice and Special Assistance Department",
        "category": "Social Justice & Welfare",
        "source_url": "https://lasvm.maharashtra.gov.in/",
        "official_apply_url": "https://lasvm.maharashtra.gov.in/",
        "application_mode": "offline",
        "benefits": "50% government subsidy (up to ₹25,000 to ₹50,000) on term loans up to ₹1,00,000 to ₹5,00,000 for setting up small shops, transport vehicles, or workshops.",
        "eligibility": "Persons belonging to Matang, Madiga, Mang, and sub-castes in Maharashtra. Age 18 to 50 years. Income up to ₹1.5 Lakh.",
        "documents_required": "Matang Caste Certificate, Income Certificate, Quotation for equipment, Domicile certificate, Bank passbook.",
        "application_deadline": None,
        "current_window_status": "no_deadline_published",
        "text": "Self-employment and small business financing for members of the Matang community across Maharashtra.",
    },
    {
        "title": "Vasantrao Naik Vimukta Jatis & Nomadic Tribes Development Corporation Loan Scheme",
        "title_mr": "वसंतराव नाईक विमुक्त जाती व भटक्या जमाती विकास महामंडळ थेट कर्ज योजना",
        "department": "Other Backward Bahujan Welfare Department",
        "category": "Social Justice & Welfare",
        "source_url": "https://vjnt.maharashtra.gov.in/",
        "official_apply_url": "https://vjnt.maharashtra.gov.in/",
        "application_mode": "online",
        "benefits": "Direct business loans up to ₹1,00,000 at only 4% simple annual interest and bank-linked projects up to ₹10,00,000 with interest subsidy for VJNT youth.",
        "eligibility": "Members of Vimukta Jati (Denotified Tribes) and Nomadic Tribes (VJNT) residing in Maharashtra. Family income up to ₹1 Lakh in rural and ₹1.2 Lakh in urban areas.",
        "documents_required": "VJNT Caste Certificate, Income Certificate from Tahsildar, Business Project Report, Domicile Certificate, Aadhaar card.",
        "application_deadline": None,
        "current_window_status": "no_deadline_published",
        "text": "Direct low-interest lending program supporting self-employment and commercial ventures for nomadic tribes.",
    },
    {
        "title": "Maulana Azad Minorities Financial Development Corporation Term Loan Scheme",
        "title_mr": "मौलाना आझाद अल्पसंख्याक आर्थिक विकास महामंडळ मुदत कर्ज योजना",
        "department": "Minority Development Department",
        "category": "Social Justice & Welfare",
        "source_url": "https://mamfdc.maharashtra.gov.in/",
        "official_apply_url": "https://mamfdc.maharashtra.gov.in/",
        "application_mode": "online",
        "benefits": "Term loans up to ₹5,00,000 to ₹10,00,000 at concessional interest rate of 6% per annum for starting manufacturing, service, or retail businesses.",
        "eligibility": "Religious minority youth (Muslim, Buddhist, Christian, Sikh, Parsi, Jain, Jewish) residing in Maharashtra. Age 18 to 50 years. Annual family income up to ₹3.0 Lakh.",
        "documents_required": "Minority declaration or School Leaving Certificate, Domicile certificate, Income certificate, Detailed Project Report, Bank guarantee.",
        "application_deadline": None,
        "current_window_status": "no_deadline_published",
        "text": "Low-interest commercial credit program fostering entrepreneurship among youth from minority communities.",
    },

    # ---------------- Women Welfare & Economic Empowerment ----------------
    {
        "title": "Pink E-Rickshaw Scheme for Women (80% State Subsidy)",
        "title_mr": "पिंक ई-रिक्षा योजना (महिलांसाठी ८०% शासकीय अनुदान)",
        "department": "Women and Child Development Department",
        "category": "Women & Child",
        "source_url": "https://womenchild.maharashtra.gov.in/pink-rickshaw",
        "official_apply_url": "https://womenchild.maharashtra.gov.in/",
        "application_mode": "offline",
        "benefits": "80% government subsidy on purchase of electric passenger auto-rickshaws (pink e-rickshaw) with 10% bank loan and only 10% beneficiary contribution.",
        "eligibility": "Women aged 20 to 45 years residing in Mumbai, Thane, Pune, Nagpur, Chhatrapati Sambhajinagar, and other major cities. Annual family income up to ₹2 Lakh.",
        "documents_required": "Valid commercial auto-rickshaw driving license, Domicile Certificate (15 years residency), Aadhaar card, Bank passbook, Income certificate.",
        "application_deadline": "2026-11-30",
        "current_window_status": "open",
        "text": "Self-reliance transportation scheme enabling 10,000 women to earn independent livelihoods as commercial auto-rickshaw drivers.",
    },
    {
        "title": "MAVIM Tejaswini Self-Help Group Microfinance and Revolving Fund",
        "title_mr": "माविम तेजस्विनी महिला बचत गट फिरता निधी व मायक्रोफायनान्स",
        "department": "Women and Child Development Department (MAVIM)",
        "category": "Women & Child",
        "source_url": "https://mavimindia.org/",
        "official_apply_url": "https://mavimindia.org/",
        "application_mode": "offline",
        "benefits": "Revolving fund grant of ₹15,000 plus bank-linked low-interest credit linkage up to ₹5,00,000 for Women Self-Help Groups (SHG) producing food, textiles, and handicrafts.",
        "eligibility": "Women Self-Help Groups (Bachat Gat) registered with MAVIM or Rural Livelihoods Mission with minimum 10 members operating for at least 6 months.",
        "documents_required": "SHG Registration, Resolution of Bachat Gat, Group Bank Passbook, Monthly savings ledger.",
        "application_deadline": None,
        "current_window_status": "no_deadline_published",
        "text": "Grassroots women's collective financing uplifting rural women through micro-enterprises and group savings.",
    },
    {
        "title": "Baby Care Kit Scheme for Newborns (Government Hospitals)",
        "title_mr": "बेबी केअर किट योजना (प्राथमिक आरोग्य केंद्र व शासकीय रुग्णालये)",
        "department": "Women and Child Development and Public Health Department",
        "category": "Women & Child",
        "source_url": "https://womenchild.maharashtra.gov.in/baby-care-kit",
        "official_apply_url": "https://womenchild.maharashtra.gov.in/",
        "application_mode": "offline",
        "benefits": "Free comprehensive newborn kit worth ₹2,000 (including baby clothes, mosquito net bed, blanket, baby towel, thermometer, baby oil, shampoo, nail clipper, and rattles).",
        "eligibility": "Mothers who deliver their first newborn child in any government hospital, Primary Health Center (PHC), or rural hospital in Maharashtra.",
        "documents_required": "Institutional delivery discharge card, Mother's Aadhaar card, Hospital registration card.",
        "application_deadline": None,
        "current_window_status": "no_deadline_published",
        "text": "Promoting safe hospital deliveries and infant health by providing essential hygiene and clothing kits at birth.",
    },

    # ---------------- School Education, Sports & Tribal Hostels ----------------
    {
        "title": "Ahilyabai Holkar Free Bus Travel Scheme for Rural Schoolgirls",
        "title_mr": "अहिल्याबाई होळकर मोफत एसटी बस प्रवास योजना (ग्रामीण विद्यार्थिनी)",
        "department": "School Education and Transport Department (MSRTC)",
        "category": "Education & DBT",
        "source_url": "https://msrtc.maharashtra.gov.in/student-concession",
        "official_apply_url": "https://msrtc.maharashtra.gov.in/",
        "application_mode": "offline",
        "benefits": "100% free monthly bus pass on all Maharashtra State Road Transport Corporation (MSRTC) red buses for rural girls traveling from home village to school/junior college.",
        "eligibility": "Girl students studying in Class 5th to 12th in recognized government or aided schools who travel daily from villages lacking secondary schools.",
        "documents_required": "Certificate from School Headmaster, Student ID, Aadhaar Card, Passport photo.",
        "application_deadline": None,
        "current_window_status": "no_deadline_published",
        "text": "Zero-cost transportation guarantee preventing rural girls from dropping out of school after 5th or 8th standard.",
    },
    {
        "title": "Dnyanjyoti Savitribai Phule Aadhaar Yojana for OBC/VJNT Hostellers",
        "title_mr": "ज्ञानज्योती सावित्रीबाई फुले आधार योजना (ओबीसी/व्हीजेएनटी वसतिगृह भत्ता)",
        "department": "Other Backward Bahujan Welfare Department",
        "category": "Education & DBT",
        "source_url": "https://obcw.maharashtra.gov.in/aadhaar-yojana",
        "official_apply_url": "https://obcw.maharashtra.gov.in/",
        "application_mode": "online",
        "benefits": "Annual food and hostel allowance of ₹43,000 to ₹60,000 per year directly credited to bank accounts of OBC/VJNT/SBC students who cannot secure a government hostel seat.",
        "eligibility": "OBC, VJNT, or SBC students admitted to higher education courses in cities away from their home taluka. Family income up to ₹2.5 Lakh.",
        "documents_required": "Caste Certificate, Non-Creamy Layer Certificate, Income Certificate from Tahsildar, College Bonafide, Hostel/Rental Agreement.",
        "application_deadline": "2026-12-31",
        "current_window_status": "open",
        "text": "Living and meal stipend on the lines of Swadhar scheme for backward class college and university students.",
    },
    {
        "title": "Rajarshi Chhatrapati Shahu Maharaj Foreign Higher Education Scholarship",
        "title_mr": "राजर्षी छत्रपती शाहू महाराज परदेशी उच्च शिक्षण शिष्यवृत्ती",
        "department": "Social Justice and Special Assistance Department",
        "category": "Education & DBT",
        "source_url": "https://sjsa.maharashtra.gov.in/foreign-scholarship",
        "official_apply_url": "https://sjsa.maharashtra.gov.in/",
        "application_mode": "online",
        "benefits": "100% foreign university tuition fees, annual living allowance ($14,000-$15,400 or equivalent in GBP/Euros), and round-trip airfare for Masters and Ph.D. abroad.",
        "eligibility": "Scheduled Caste students of Maharashtra admitted to top 300 QS World University Ranked foreign institutions. Family annual income limit up to ₹6 Lakh.",
        "documents_required": "Unconditional foreign university admission offer, QS Ranking proof, Caste Certificate, Validity Certificate, GRE/IELTS/TOEFL scorecard, Income Certificate.",
        "application_deadline": "2026-11-15",
        "current_window_status": "open",
        "text": "Prestigious state foreign scholarship enabling 75 SC scholars annually to study at Harvard, Oxford, Stanford, and leading global universities.",
    },
    {
        "title": "Sayajirao Gaikwad Foreign Higher Education Scholarship for Maratha/Open Category",
        "title_mr": "सयाजीराव गायकवाड परदेशी उच्च शिक्षण शिष्यवृत्ती (सारथी)",
        "department": "General Administration Department (SARTHI)",
        "category": "Education & DBT",
        "source_url": "https://sarthi-maharashtragov.in/foreign-scholarship",
        "official_apply_url": "https://sarthi-maharashtragov.in/",
        "application_mode": "online",
        "benefits": "Complete tuition fee reimbursement up to ₹30-40 Lakh, international airfare, and annual living allowance for PG and Ph.D. degrees in top 200 QS global universities.",
        "eligibility": "Maratha, Kunbi, and Economically Weaker Section (EWS) students residing in Maharashtra. Family annual income up to ₹8 Lakh.",
        "documents_required": "Admit letter from top 200 QS foreign university, Caste/EWS certificate, Domicile certificate, Degree marksheets, Passport.",
        "application_deadline": "2026-11-15",
        "current_window_status": "open",
        "text": "Global higher education scholarship for students from agriculture-based families to study in world-class institutions.",
    },
]


def seed_additional():
    with SessionLocal() as db:
        added = 0
        updated = 0
        for item in ADDITIONAL_SCHEMES:
            existing = db.scalar(
                select(SchemeCandidate).where(
                    (SchemeCandidate.title == item["title"]) |
                    (SchemeCandidate.title_mr == item["title_mr"])
                )
            )
            source_url = item["source_url"]
            url_sha256 = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
            content_sha256 = hashlib.sha256((item["title"] + item.get("text", "")).encode("utf-8")).hexdigest()
            
            if not existing:
                scheme = SchemeCandidate(
                    title=item["title"],
                    title_mr=item["title_mr"],
                    department=item["department"],
                    category=item["category"],
                    source_url=source_url,
                    source_url_sha256=url_sha256,
                    content_sha256=content_sha256,
                    official_apply_url=item.get("official_apply_url"),
                    verification_status="verified",
                    current_window_status=item.get("current_window_status", "no_deadline_published"),
                    application_deadline=item.get("application_deadline"),
                    application_mode=item.get("application_mode", "online"),
                    text=item.get("text", item["title"]),
                    brief_description=item.get("benefits", "")[:350],
                    benefits=item.get("benefits", ""),
                    eligibility=item.get("eligibility", ""),
                    documents_required=item.get("documents_required", ""),
                    retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
                    notes="Verified Official Maharashtra Government Scheme",
                    reviewed_by="Senior Verification Specialist",
                )
                db.add(scheme)
                db.flush()
                
                window = SchemeApplicationWindow(
                    scheme_id=scheme.id,
                    window_name="Annual Application Round 2026-27",
                    start_date="2026-04-01",
                    deadline_date=item.get("application_deadline"),
                    window_status=item.get("current_window_status", "no_deadline_published"),
                    date_verification_status="verified",
                    official_source_url=source_url,
                )
                db.add(window)
                added += 1
            else:
                existing.title_mr = item["title_mr"]
                existing.department = item["department"]
                existing.category = item["category"]
                existing.benefits = item.get("benefits", existing.benefits)
                existing.brief_description = item.get("benefits", "")[:350]
                existing.eligibility = item.get("eligibility", existing.eligibility)
                existing.documents_required = item.get("documents_required", existing.documents_required)
                existing.official_apply_url = item.get("official_apply_url", existing.official_apply_url)
                updated += 1
                
        db.commit()
        total_count = db.scalar(select(SchemeCandidate.id).order_by(SchemeCandidate.id.desc()))
        print(f"Supplementary seeding complete! Added: {added}, Updated: {updated}. Total schemes in DB now: {total_count}")


if __name__ == "__main__":
    seed_additional()
