COMMON_HINTS = {
    "satis": [
        "Satis teklifleri genellikle Satis uygulamasinda Teklifler menusu altinda yonetilir.",
        "Bir teklifi siparise cevirmeden once musteri, teslimat adresi ve fiyat listesini kontrol etmek faydalidir.",
    ],
    "satinalma": [
        "Satin alma akisinda once teklif talebi veya satin alma siparisi olusturulur, sonra teslimatlar ve faturalar takip edilir.",
        "Tedarikci fiyatlari ve teslim terminleri farkli ise urun kartindaki satin alma sekmesini kontrol etmek gerekir.",
    ],
    "stok": [
        "Stok hareketlerinde Operasyonlar, Transferler ve Urunler menuleri en sik kullanilan alanlardir.",
        "Miktar uyusmazliginda urun karti, stok lokasyonu ve bekleyen transferler birlikte kontrol edilmelidir.",
    ],
    "muhasebe": [
        "Muhasebe islemlerinde taslak kayitlarin onaylanip onaylanmadigi ve ilgili gunluk secimi kritik oneme sahiptir.",
        "Odeme eslestirme ve mutabakat sorunlarinda musteri veya tedarikci hesap hareketleri de kontrol edilmelidir.",
    ],
    "crm": [
        "CRM firsatlari genellikle boru hatti ekranindan asamalar arasinda tasinir.",
        "Beklenen gelir, sorumlu kullanici ve planlanan aktivite bilgileri gunluyse takip daha saglikli olur.",
    ],
}


def build_hint_block(question):
    question_lower = (question or "").lower()
    hints = []
    keyword_map = {
        "satis": ["satis", "teklif", "siparis", "quotation", "order"],
        "satinalma": ["satin alma", "satinalma", "tedarik", "purchase"],
        "stok": ["stok", "envanter", "depo", "transfer", "inventory"],
        "muhasebe": ["muhasebe", "fatura", "odeme", "mutabakat", "accounting"],
        "crm": ["crm", "firsat", "lead", "opportunity"],
    }
    for topic, keywords in keyword_map.items():
        if any(keyword in question_lower for keyword in keywords):
            hints.extend(COMMON_HINTS[topic])
    return hints

