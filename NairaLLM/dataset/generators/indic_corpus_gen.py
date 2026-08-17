"""
Comprehensive Indic Linguistic & Technical Corpus Generator for Dataset A.
Generates comprehensive Hindi and Hinglish texts covering Indian science, language modeling, cloud architecture, and software engineering.
"""

from __future__ import annotations

from typing import Any


def get_indic_corpus_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "Comprehensive Indic linguistic and technical exposition",
            },
        })

    # Hindi Articles
    add(
        "sem_hi_041",
        "hindi_linguistics",
        "hi",
        "भारतीय अंतरिक्ष अनुसंधान संगठन (इसरो - ISRO) की स्थापना 1969 में डॉ. विक्रम साराभाई के दूरदर्शी नेतृत्व में की गई थी। इसरो ने भारत को अंतरिक्ष प्रौद्योगिकी के क्षेत्र में एक वैश्विक महाशक्ति के रूप में स्थापित किया है। चंद्रयान-3 मिशन के माध्यम से भारत चंद्रमा के दक्षिणी ध्रुव पर सॉफ्ट लैंडिंग करने वाला विश्व का पहला देश बना। इसके साथ ही मार्स ऑर्बिटर मिशन (मंगलयान) ने अपने पहले ही प्रयास में मंगल ग्रह की कक्षा में सफलतापूर्वक प्रवेश करके विश्व रिकॉर्ड बनाया। इसरो के पीएसएलवी (PSLV) और एलवीएम-3 (LVM-3) प्रक्षेपण यान उपग्रहों को सटीक कक्षाओं में स्थापित करने में अपनी विश्वसनीयता और लागत-कुशलता के लिए वैश्विक स्तर पर प्रसिद्ध हैं।",
        "ISRO Indian space exploration and Chandrayaan missions in Hindi",
    )

    add(
        "sem_hi_042",
        "hindi_linguistics",
        "hi",
        "भाषा विज्ञान में 'पद-परिचय' किसी वाक्य में प्रयुक्त प्रत्येक शब्द (पद) के व्याकरणिक स्वरूप, उसके प्रकार, लिंग, वचन, कारक और अन्य शब्दों के साथ उसके संबंध को स्पष्ट करने की प्रक्रिया है। उदाहरण के लिए, वाक्य 'मोहन ने सुंदर गीत गाया' में 'मोहन' व्यक्तिवाचक संज्ञा, पुल्लिंग, एकवचन और कर्ता कारक है (ने परसर्ग के साथ)। 'सुंदर' गुणवाचक विशेषण है जो 'गीत' विशेष्य की विशेषता बताता है। 'गीत' जातिवाचक संज्ञा, कर्म कारक है, और 'गाया' सकर्मक क्रिया, भूतकाल, पुल्लिंग, एकवचन है। पद-परिचय का अध्ययन व्याकरणिक शुद्धता और भाषा की गहन संरचना को समझने का मुख्य आधार है।",
        "Hindi grammar Pada Parichaya (Morphological syntactic parsing) in Hindi",
    )

    add(
        "sem_hi_043",
        "hindi_linguistics",
        "hi",
        "मशीन ट्रांसलेशन (यांत्रिक अनुवाद) और बहुभाषी भाषा मॉडल (Multilingual LLMs) में टोकनाइज़ेशन एक अत्यंत महत्वपूर्ण प्रथम चरण है। जब कोई मॉडल हिंदी देवनागरी पाठ को प्रोसेस करता है, तो बाइट-लेयर बीपीई (Byte-Level BPE) टोकनाइज़र देवनागरी के बहु-बाइट यूटीएफ-8 कोडपॉइंट्स को संयोजित करता है। यदि टोकनाइज़र की शब्दावली में सामान्य हिंदी अक्षरों और शब्दों के लिए समर्पित टोकन शामिल नहीं होते, तो टोकन फर्टिलिटी (Token Fertility) दर बढ़ जाती है, जिससे मॉडल की प्रसंस्करण गति धीमी हो जाती है और अनुमानित संदर्भ लंबाई (Context Length) जल्दी समाप्त हो जाती है।",
        "Multilingual NLP and Devanagari Byte-Level BPE tokenization in Hindi",
    )

    add(
        "sem_hi_044",
        "hindi_linguistics",
        "hi",
        "कंप्यूटर सुरक्षा में 'क्रिप्टोग्राफ़िक हैश फ़ंक्शन' अपरिवर्तनीय गणितीय एल्गोरिदम हैं जो किसी भी आकार के डेटा इनपुट को एक निश्चित लंबाई के अद्वितीय डाइजेस्ट में परिवर्तित करते हैं। एक सुरक्षित हैश फ़ंक्शन में हिमस्खलन प्रभाव (Avalanche Effect) होना अनिवार्य है—यदि इनपुट में केवल एक बिट का भी परिवर्तन किया जाए, तो परिणामी हैश मान में 50 प्रतिशत से अधिक बिट्स बदल जाने चाहिए। एसएचए-256 (SHA-256) का व्यापक उपयोग पासवर्ड भंडारण, डिजिटल हस्ताक्षर, डेटा अखंडता सत्यापन और ब्लॉकचेन ब्लॉक सत्यापन में किया जाता है।",
        "Cryptographic hash functions, Avalanche effect and SHA-256 in Hindi",
    )

    add(
        "sem_hi_045",
        "hindi_linguistics",
        "hi",
        "भारतीय शास्त्रीय संगीत परंपरा दो प्रमुख शैलियों में विभाजित है: उत्तर भारत की 'हिंदुस्तानी संगीत' और दक्षिण भारत की 'कर्नाटक संगीत'। हिंदुस्तानी संगीत में राग और ताल का ढांचा अत्यंत समृद्ध है, जिसमें 10 प्रमुख थाटों (कल्याण, बिलावल, खमाज, भैरव, भैरवी, आसावरी, तोड़ी, पूर्वी, मारवा, काफी) के अंतर्गत रागों का वर्गीकरण किया गया है। प्रत्येक राग का अपना विशिष्ट वादी (मुख्य स्वर), संवादी, आरोह, अवरोह और गायन का निश्चित समय होता है, जो प्रकृति, ऋतुओं और मानवीय मनोभावों के साथ गहरा सामंजस्य स्थापित करता है।",
        "Indian classical music ragas and Hindustani musical theory in Hindi",
    )

    # Hinglish Articles
    add(
        "sem_hing_039",
        "hinglish_discourse",
        "hinglish",
        "Modern cloud databases me High Availability (HA) aur Disaster Recovery (DR) architect karte time Multi-AZ (Availability Zone) deployment aur asynchronous cross-region read replicas configure kiye jaate hain. Primary database node pe automatic failover enable hota hai jo heartbeats monitor karta hai. Agar primary zone me power outage ya network partition hota hai, toh standby replica automatically promote hoke primary ban jata hai bina data loss ke, aur DNS records dynamically update ho jaate hain.",
        "Cloud database Multi-AZ high availability and automated failover in Hinglish",
    )

    add(
        "sem_hing_040",
        "hinglish_discourse",
        "hinglish",
        "Python web development me ASGI (Asynchronous Server Gateway Interface) standard WSGI (Web Server Gateway Interface) ka modern successor hai. WSGI synchronous single-request-per-worker model pe chalta tha jo WebSockets aur long-polling connections efficiently support nahi kar pata tha. Uvicorn aur Hypercorn jaise ASGI servers asynchronous event loop use karke high concurrency support karte hain, jisse FastAPI aur modern Django channels easily thousands of live concurrent connections handle kar lete hain.",
        "ASGI vs WSGI web server standards and Uvicorn concurrency in Hinglish",
    )

    add(
        "sem_hing_041",
        "hinglish_discourse",
        "hinglish",
        "Large-scale software systems me Feature Flags (Toggles) use karna continuous delivery ka core pillar hai. LaunchDarkly ya Unleash jaisa feature flag system code deployment aur feature release ko decouple kar deta hai. Naya feature production codebase me safely merge ho jata hai lekin toggle disabled rehta hai. Pehle internal team members aur 5% beta users ke liye feature enable karke metrics aur error logs monitor kiye jaate hain (Canary release), aur sab kuch stable hone ke baad 100% users ke liye rollout kar diya jata hai.",
        "Feature flags, canary releases, and progressive delivery in Hinglish",
    )

    add(
        "sem_hing_042",
        "hinglish_discourse",
        "hinglish",
        "React Server Components (RSC) modern frontend architecture me server aur client rendering boundaries ko redefine karte hain. Server Components sirf server pe execute hote hain aur zero client-side JavaScript bundle add karte hain, directly database se data fetch karke pre-rendered UI send karte hain. Client Components (`'use client'`) sirf un interactive widgets ke liye use kiye jaate hain jahan browser events, `useState`, ya `useEffect` hooks required hote hain, jisse initial page load time drastically fast ho jata hai.",
        "React Server Components (RSC) and bundle size optimization in Hinglish",
    )

    return samples
