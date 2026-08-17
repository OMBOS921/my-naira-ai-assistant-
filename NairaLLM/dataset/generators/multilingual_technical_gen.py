"""
Multilingual Technical Deep-Dive Domain Generator for Dataset A.
Generates comprehensive Hindi and Hinglish technical narratives across cloud, security, algorithms, and distributed computing.
"""

from __future__ import annotations

from typing import Any


def get_multilingual_technical_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, domain: str, lang: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": domain,
            "language": lang,
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Multilingual technical systems narrative",
            },
        })

    # Hindi Deep Dives
    add(
        "sem_hi_046",
        "databases",
        "hi",
        "रिलेशनल डेटाबेस में 'क्वेरी ऑप्टिमाइज़र' एसक्यूएल (SQL) क्वेरी को सबसे कुशल भौतिक निष्पादन योजना (Physical Execution Plan) में बदलने का कार्य करता है। जब कोई जटिल SELECT क्वेरी कई तालिकाओं के जॉइन (Join) और WHERE शर्तों के साथ निष्पादित की जाती है, तो ऑप्टिमाइज़र डेटाबेस कैटलॉग में संग्रहीत तालिका सांख्यिकी (Table Statistics), कॉलम हिस्टोग्राम, और इंडेक्स चयनात्मकता (Selectivity) का विश्लेषण करता है। यह विभिन्न जॉइन एल्गोरिदम—जैसे नेस्टेड लूप जॉइन, हैश जॉइन, और सॉर्ट-मर्ज जॉइन—के अनुमानित इनपुट/आउटपुट (I/O) और सीपीयू लागत की गणना करता है और न्यूनतम लागत वाली योजना का चयन करता है।",
        "Relational query optimizer and cost estimation in Hindi",
    )

    add(
        "sem_hi_047",
        "operating_systems",
        "hi",
        "लिनक्स ऑपरेटिंग सिस्टम में फाइल सिस्टम की संरचना 'आईनोड' (Inode - Index Node) पर आधारित होती है। आईनोड एक डेटा संरचना है जो फ़ाइल के मेटाडेटा को संग्रहीत करती है, जिसमें फ़ाइल का आकार, डिस्क ब्लॉक पते, फ़ाइल प्रकार, अनुमतियाँ (Permissions), स्वामी यूआईडी/जीआईडी, और समय-चिह्न (atime, mtime, ctime) शामिल होते हैं। ध्यान देने योग्य बात यह है कि आईनोड में फ़ाइल का नाम शामिल नहीं होता; डायरेक्टरी स्वयं एक विशेष फ़ाइल होती है जो फ़ाइल नामों को उनके संबंधित आईनोड नंबरों से मैप करती है। हार्ड लिंक (Hard Link) केवल एक ही आईनोड को कई नामों से जोड़ने की अनुमति देता है।",
        "Linux filesystem Inode structure and hard links in Hindi",
    )

    add(
        "sem_hi_048",
        "security",
        "hi",
        "वेब सुरक्षा में 'क्रॉस-साइट रिक्वेस्ट फोर्जरी' (CSRF) एक ऐसा हमला है जिसमें एक दुर्भावनापूर्ण वेबसाइट उपयोगकर्ता के ब्राउज़र को उस वेबसाइट पर अनधिकृत क्रियाएं (जैसे पासवर्ड बदलना, धनराशि स्थानांतरित करना) निष्पादित करने के लिए बाध्य करती है जहां उपयोगकर्ता पहले से प्रमाणित है। चूंकि ब्राउज़र स्वचालित रूप से प्रत्येक अनुरोध के साथ प्रमाणीकरण कुकीज़ संलग्न करता है, सर्वर यह भेद नहीं कर पाता कि अनुरोध वैध उपयोगकर्ता द्वारा किया गया है या किसी छिपे हुए हमले द्वारा। सीएसआरएफ हमलों से बचाव के लिए 'एंटी-सीएसआरएफ टोकन' (CSRF Token) और कुकीज़ के लिए 'SameSite=Strict' या 'SameSite=Lax' सुरक्षा विशेषताओं का उपयोग अनिवार्य है।",
        "CSRF web vulnerability and anti-CSRF token defense in Hindi",
    )

    add(
        "sem_hi_049",
        "algorithms",
        "hi",
        "कंप्यूटर विज्ञान में 'सॉर्टिंग एल्गोरिदम' डेटा को एक विशिष्ट क्रम (आरोही या अवरोही) में व्यवस्थित करने की मूलभूत तकनीकें हैं। 'मर्ज सॉर्ट' (Merge Sort) डिवाइड-एंड-कॉन्कर सिद्धांत पर कार्य करता है और सभी स्थितियों में O(N log N) समय जटिलता और स्थिरता (Stability) की गारंटी देता है। दूसरी ओर, 'क्विक सॉर्ट' (Quick Sort) इन-प्लेस पार्टीशनिंग का उपयोग करता है और औसत स्थिति में O(N log N) समय में निष्पादित होता है, यद्यपि सबसे खराब स्थिति में इसकी जटिलता O(N^2) हो सकती है। व्यावहारिक प्रणालियों में, दोनों के लाभों को मिलाकर 'टिमसॉर्ट' (Timsort) जैसे हाइब्रिड एल्गोरिदम बनाए गए हैं जिनका उपयोग पायथन और जावा में किया जाता है।",
        "Sorting algorithms (Merge Sort, Quick Sort, Timsort) in Hindi",
    )

    # Hinglish Deep Dives
    add(
        "sem_hing_043",
        "software_engineering",
        "hinglish",
        "Microservices architecture me asynchronous event messaging ke liye RabbitMQ vs Apache Kafka choose karte time throughput aur message delivery semantics evaluate karni padti hain. RabbitMQ ek traditional smart-broker message queue hai jo AMQP protocol, complex exchange routing (direct, topic, fanout), aur per-message acknowledgments support karta hai, jo task queues aur transactional processing ke liye perfect hai. Apache Kafka ek distributed append-only commit log hai jo high-throughput event streaming, event replayability, aur massive horizontal partition scaling provide karta hai.",
        "RabbitMQ vs Apache Kafka architectural comparison in Hinglish",
    )

    add(
        "sem_hing_044",
        "databases",
        "hinglish",
        "High-scale distributed systems me database connection pooling properly configure karna resource exhaustion prevent karta hai. Application server ka har worker thread agar naya direct database TCP connection establish karega, toh database memory me excessive connection context allocate hone lagega. HikariCP ya PgBouncer jaisa connection pooler pre-established connections maintain karta hai, connection acquisition latency sub-millisecond karta hai, aur database max connection limits enforce karke overload hone se bachata hai.",
        "Database connection pooling and PgBouncer architecture in Hinglish",
    )

    add(
        "sem_hing_045",
        "security",
        "hinglish",
        "Web applications me Secure by Design principles implement karte time HTTP security response headers configure karna first defense layer hai. `X-Frame-Options: DENY` clickjacking attacks ko block karta hai, `X-Content-Type-Options: nosniff` MIME sniffing prevent karta hai, aur `Referrer-Policy: strict-origin-when-cross-origin` sensitive URL parameters ko external sites pe leak hone se rokkta hai. Saath me HSTS aur CSP headers combine karke comprehensive defense-in-depth security posture banta hai.",
        "HTTP security headers defense-in-depth in Hinglish",
    )

    add(
        "sem_hing_046",
        "programming",
        "hinglish",
        "TypeScript me advanced type manipulation ke liye Conditional Types, Mapped Types, aur Template Literal Types powerful tools hain. Conditional types (`T extends U ? X : Y`) runtime logic ke bina compile-time type branch enable karte hain. `Pick<T, K>`, `Omit<T, K>`, aur `ReturnType<T>` jaise built-in utility types complex API responses ko strongly type-safe banate hain, jisse runtime null pointer exceptions aur property access bugs development phase me hi eliminate ho jaate hain.",
        "TypeScript advanced type manipulation and utility types in Hinglish",
    )

    return samples
