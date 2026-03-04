import os
"""
ViewMonitor Pro API v3.3 — Küresel OSINT
══════════════════════════════════════════
  ✔ 120+ RSS kaynağı (TR, KKTC, Kıbrıs, Orta Doğu, Asya-Pasifik, ABD, İsrail, OSINT)
  ✔ 60+ Telegram OSINT kanalı
  ✔ 35+ Nitter/Twitter OSINT hesabı
  ✔ GDELT global çatışma olayları
  ✔ SQLite + SSE + Background Scheduler
  ✔ Telegram 6 saat filtresi
  ✔ Hash-bazlı duplicate kontrolü
"""

import asyncio, csv, hashlib, io, json, logging, logging.handlers
import random
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator, List, Optional

import aiosqlite, feedparser, httpx, uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langdetect import LangDetectException, detect

# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════
TWITTER_BEARER         = "AAAAAAAAAAAAAAAAAAAAAF7h7wEAAAAAVQgKThE8b8pSB64Tac39ujfTOrY=3unpaziAEF0VoKIusaXkFeeyUbEPmkU9k95hd88yaQOmh9Thle"
DB_PATH                = os.environ.get("DB_PATH", "/tmp/viewmonitor.db")
LOG_PATH               = "viewmonitor.log"
FETCH_INTERVAL         = 8    # saniye — her 8sn yeni kaynak taranır
MAX_DB_ROWS            = 8000
TELEGRAM_MAX_YAS_SAAT  = 6

# ══════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════
logger = logging.getLogger("VM")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
_fh  = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
_fh.setFormatter(_fmt)
_ch  = logging.StreamHandler(); _ch.setFormatter(_fmt)
logger.addHandler(_fh); logger.addHandler(_ch)

# ══════════════════════════════════════════════
# LOKASYONLAR
# ══════════════════════════════════════════════
KRITIK_LOKASYONLAR = {
    # Türkiye
    "istanbul":[41.0082,28.9784],"ankara":[39.9334,32.8597],"izmir":[38.4192,27.1287],
    "bursa":[40.1885,29.0610],"antalya":[36.8969,30.7133],"adana":[37.0000,35.3213],
    "konya":[37.8667,32.4833],"gaziantep":[37.0662,37.3833],"kayseri":[38.7205,35.4826],
    "mersin":[36.7921,34.6210],"şanlıurfa":[37.1591,38.7969],"diyarbakır":[37.9144,40.2306],
    "trabzon":[41.0015,39.7178],"samsun":[41.2928,36.3313],"hatay":[36.2025,36.1606],
    "malatya":[38.3552,38.3095],"erzurum":[39.9078,41.2769],"eskişehir":[39.7767,30.5206],
    "kocaeli":[40.8533,29.8815],"sakarya":[40.7731,30.4043],"edirne":[41.6818,26.5623],
    "çanakkale":[40.1553,26.4142],"van":[38.4891,43.4089],"batman":[37.8812,41.1351],
    "mardin":[37.3212,40.7245],"şırnak":[37.5164,42.4611],"siirt":[37.9333,41.9500],
    "hakkari":[37.5744,43.7408],"muş":[38.9462,41.4922],"bingöl":[38.8833,40.5000],
    "tunceli":[39.1081,39.5481],"elazığ":[38.6810,39.2264],"bitlis":[38.3947,42.1232],
    "ağrı":[39.7191,43.0503],"iğdır":[39.9167,44.0333],"kilis":[36.7184,37.1212],
    "kahramanmaraş":[37.5753,36.9228],"osmaniye":[37.0742,36.2467],"adıyaman":[37.7648,38.2786],
    # KKTC
    "lefkoşa":[35.1856,33.3823],"gazimağusa":[35.1264,33.9426],"girne":[35.3411,33.3183],
    # Güney Kıbrıs
    "nicosia":[35.1856,33.3823],"limassol":[34.6851,33.0330],"larnaca":[34.9229,33.6233],
    # Orta Doğu / İsrail-Filistin
    "gazze":[31.5017,34.4668],"gaza":[31.5017,34.4668],"rafah":[31.2803,34.2443],
    "han yunis":[31.3479,34.3017],"nablus":[32.2211,35.2544],"ramallah":[31.9038,35.2034],
    "jenin":[32.4573,35.2969],"tulkarm":[32.3105,35.0286],"kalkilya":[32.1866,34.9709],
    "tel aviv":[32.0853,34.7818],"kudüs":[31.7683,35.2137],"jerusalem":[31.7683,35.2137],
    "haifa":[32.7940,34.9896],"netanya":[32.3226,34.8564],"askelon":[31.6688,34.5743],
    "sderot":[31.5241,34.5967],"eilat":[29.5577,34.9519],
    "beyrut":[33.8938,35.5018],"beirut":[33.8938,35.5018],"sur":[33.2705,35.2038],
    "baalbek":[34.0040,36.2118],"zahle":[33.8499,35.9019],"sidon":[33.5621,35.3714],
    "şam":[33.5138,36.2765],"damascus":[33.5138,36.2765],"halep":[36.2021,37.1343],
    "aleppo":[36.2021,37.1343],"humus":[34.7324,36.7137],"idlib":[35.9310,36.6329],
    "derizor":[35.3325,40.1408],"haseke":[36.4943,40.7421],"qamishli":[37.0509,41.2273],
    "bağdat":[33.3152,44.3661],"baghdad":[33.3152,44.3661],"musul":[36.3350,43.1190],
    "mosul":[36.3350,43.1190],"basra":[30.5085,47.7804],"erbil":[36.1911,44.0092],
    "kerkük":[35.4681,44.3922],"falluja":[33.3500,43.7833],"ramadi":[33.4258,43.3013],
    "tahran":[35.6892,51.3890],"tehran":[35.6892,51.3890],"mashhad":[36.2972,59.6067],
    "isfahan":[32.6546,51.6680],"tabriz":[38.0801,46.2919],"shiraz":[29.5918,52.5837],
    "san'a":[15.3694,44.1910],"aden":[12.7855,45.0187],"hudeyde":[14.7978,42.9450],
    "marib":[15.4606,45.3391],"taiz":[13.5769,44.0177],
    "riyad":[24.6877,46.7219],"riyadh":[24.6877,46.7219],"jeddah":[21.5433,39.1728],
    "dubai":[25.2048,55.2708],"abu dhabi":[24.4539,54.3773],"doha":[25.2854,51.5310],
    # Ukrayna / Rusya / Kafkasya
    "kyiv":[50.4501,30.5234],"kharkiv":[49.9935,36.2304],"kherson":[46.6354,32.6169],
    "zaporizhzhia":[47.8388,35.1396],"dnipro":[48.4647,35.0462],"odessa":[46.4825,30.7233],
    "lviv":[49.8397,24.0297],"mariupol":[47.0971,37.5433],"bakhmut":[48.5956,38.0001],
    "avdiivka":[47.9572,37.7554],"donetsk":[47.9960,37.8028],"luhansk":[48.5740,39.3078],
    "moskova":[55.7558,37.6173],"moscow":[55.7558,37.6173],"kırım":[44.9521,34.1024],
    "belgorod":[50.5958,36.5875],"kursk":[51.7304,36.1927],"bryansk":[53.2434,34.3640],
    "tiflis":[41.6938,44.8015],"bakü":[40.4093,49.8671],"yerevan":[40.1872,44.5152],
    # ABD / Batı
    "washington":[38.9072,77.0369],"new york":[40.7128,74.0060],"los angeles":[34.0522,118.2437],
    "chicago":[41.8781,87.6298],"miami":[25.7617,80.1918],"houston":[29.7604,95.3698],
    # Asya-Pasifik
    "beijing":[39.9042,116.4074],"şanghay":[31.2304,121.4737],"hong kong":[22.3193,114.1694],
    "taipei":[25.0330,121.5654],"taiwan":[25.0330,121.5654],"pyongyang":[39.0392,125.7625],
    "seoul":[37.5665,126.9780],"tokyo":[35.6762,139.6503],"osaka":[34.6937,135.5023],
    "delhi":[28.6139,77.2090],"mumbai":[19.0760,72.8777],"islamabad":[33.7294,73.0931],
    "karachi":[24.8607,67.0011],"kabul":[34.5553,69.2075],"yangon":[16.8661,96.1951],
    "dhaka":[23.8103,90.4125],"colombo":[6.9271,79.8612],"manila":[14.5995,120.9842],
    "jakarta":[6.2088,106.8456],"bangkok":[13.7563,100.5018],"singapore":[1.3521,103.8198],
    "kuala lumpur":[3.1390,101.6869],"hanoi":[21.0285,105.8542],"ho chi minh":[10.8231,106.6297],
    # Afrika
    "hartum":[15.5007,32.5599],"mogadishu":[2.0469,45.3182],"addis ababa":[9.0320,38.7469],
    "nairobi":[1.2921,36.8219],"tripoli":[32.9081,13.1875],"benghazi":[32.1167,20.0667],
    "bamako":[12.6392,8.0029],"niamey":[13.5137,2.1098],"ndjamena":[12.1048,15.0440],
    "kano":[12.0022,8.5920],"lagos":[6.5244,3.3792],"kinshasa":[4.3317,15.3212],
}

# ══════════════════════════════════════════════
# NITTER INSTANCES
# ══════════════════════════════════════════════
NITTER_INSTANCES = [
    "https://nitter.privacydev.net","https://nitter.poast.org",
    "https://nitter.1d4.us","https://nitter.rawbit.ninja",
    "https://nitter.unixfox.eu","https://xcancel.com",
    "https://nitter.cz","https://nitter.kavin.rocks",
]

NITTER_HESAPLARI = [
    # Büyük medya
    "BBCWorld","Reuters","AP","AJEnglish","trtworld","CNN","AFP","TheGuardian",
    "nytimes","AlArabiya_Eng","Jerusalem_Post","TimesofIsrael","HaaretzEnglish",
    "Middle_East_Eye","iran_intl","KurdistanPM",
    # Breaking/Anlık
    "Breaking911","BNONews","disclosetv","BreakingNLive","AlertsX_","newsbreaking_xl",
    "ReutersAlerts","BBCBreaking","UNNews",
    # OSINT / Çatışma / İstihbarat
    "OSINTdefender","IntelCrab","wartranslated","nexta_tv","GeoConfirmed",
    "AuroraIntel","UAWeapons","sentdefender","Intel_Sky","KyivIndependent",
    "Osinttechnical","TpyxaNews","intelslava","DefMon3","WarTranslated",
    "Conflicts","Archer83Able","RALee85","IranIntlBrk","Walla_news",
    # İnsani / BM
    "UN_News_Centre","UNHCR","ICRC","MSF","Refugees",
    # Türkçe
    "trthabertr","AnadoluAjansi","sondakika_haber","cumhuriyetgzt",
]

# ══════════════════════════════════════════════
# TELEGRAM KANALLARI — 60+
# ══════════════════════════════════════════════
TELEGRAM_KANALLARI = [
    # Türkçe haber
    "trthabertr","anadoluajansi","sonhabertr","milliyet","hurriyet",
    "cnnturktr","ntv_haber","sabahgazetesi","haberturktv","cumhuriyetgzt",
    # OSINT / Çatışma
    "insiderpaper","disclosetv","BNONews","nexta_live","QudsN",
    "wartranslated","intelslava","OSINTua","trolikua","rybar",
    "readovkanews","militarylandnet","konflikt_news","UkraineNow",
    "IntelSlava","Strelkov_DD","wargonzo","boris_rozhin","SolovievLive",
    # Orta Doğu / İsrail / Filistin
    "abna_farsi","qudsna","PalestineResistance","Gaza_Now","GazaTelegram",
    "Hamas_Gaza","AlMayadeenNews","Al_Mayadeen_Ar","qassam1brigades",
    "Islamic_Jihad_Gaza","alqassam","alresala","Palestine_channel",
    "israelidefense","IsraeliPM","idf_official","kann_news","N12News",
    "walla_news_il","ynet_news",
    # Rusya / Ukrayna
    "rybar","rlz_the_spirit","milchronicles","Slavyangrad",
    "KyivPost_official","UkraineWorldMedia","DefenceUA",
    # Asya / Dünya
    "cnnenglish","bbcnews","aljazeera_eng","dwnewsarabic",
    "irna_persian","PressTV","MEEonline",
    # İran
    "IranIntl","IranWire","irna_official",
    # Asya-Pasifik
    "IndiaToday","ndtv","PakistanToday","NHKnews",
    "TaiwanEnglishNews","TheirrawaddyNews","BangkokPost",
    # ABD / Batı
    "APenglish","BBCBreaking","AxiosNews",
    "TheHillNews","NBCNews","ABCnews",
    # Afrika
    "SudanNews","SomaliaNews","EthiopiaUpdate","LibyaNow","SahelIntel",
    # Latin Amerika
    "TeleSUR","VenezuelaNews","BrazilBreaking",
    # Ek OSINT
    "CalibreObscura","GeoConfirmedOSINT",
    "AuroraIntelligence","SpecialOpsNews",
]

# ══════════════════════════════════════════════
# RSS KAYNAKLARI — 130+
# ══════════════════════════════════════════════
RSS_KAYNAKLARI = [
    # ─── Türk Ulusal ───
    {"isim":"AA Güncel",        "url":"https://www.aa.com.tr/tr/rss/default?cat=guncel",          "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"AA Son Dakika",    "url":"https://www.aa.com.tr/tr/rss/default?cat=sondakika",       "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"AA Dünya",         "url":"https://www.aa.com.tr/tr/rss/default?cat=dunya",           "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"AA Güvenlik",      "url":"https://www.aa.com.tr/tr/rss/default?cat=guvenlik",        "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"TRT Haber",        "url":"https://www.trthaber.com/sondakika.rss",                   "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"TRT Dünya",        "url":"https://www.trthaber.com/dunya.rss",                       "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"NTV Gündem",       "url":"https://www.ntv.com.tr/gundem.rss",                        "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"NTV Dünya",        "url":"https://www.ntv.com.tr/dunya.rss",                         "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"CNN Türk",         "url":"https://www.cnnturk.com/feed/rss/news",                    "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Hürriyet Gündem",  "url":"https://www.hurriyet.com.tr/rss/gundem",                   "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Hürriyet Dünya",   "url":"https://www.hurriyet.com.tr/rss/dunya",                    "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Sabah",            "url":"https://www.sabah.com.tr/rss/anasayfa.xml",                "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Sabah Dünya",      "url":"https://www.sabah.com.tr/rss/dunya.xml",                   "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Milliyet",         "url":"https://www.milliyet.com.tr/rss/rssnew/gundemrss.xml",     "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Sözcü",            "url":"https://www.sozcu.com.tr/rss/son-dakika.xml",              "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Cumhuriyet",       "url":"https://www.cumhuriyet.com.tr/rss/son_dakika.xml",         "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Habertürk",        "url":"https://www.haberturk.com/rss",                            "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"BirGün",           "url":"https://www.birgun.net/rss",                               "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Yeni Şafak",       "url":"https://www.yenisafak.com/rss",                            "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Star Gazete",      "url":"https://www.star.com.tr/rss/rss.asp",                      "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    {"isim":"Dünya",            "url":"https://www.dunya.com/rss",                                "dil":"tr","bayrak":"🇹🇷","kat":"tr"},
    # ─── KKTC ───
    {"isim":"Kıbrıs Postası",   "url":"https://www.kibrispostasi.com/index.php/rss",              "dil":"tr","bayrak":"🇹🇷","kat":"kktc"},
    {"isim":"Yeni Kıbrıs",      "url":"https://www.yenikibris.com/rss.xml",                       "dil":"tr","bayrak":"🇹🇷","kat":"kktc"},
    {"isim":"Havadis Kıbrıs",   "url":"https://www.havadiskibris.com/rss",                        "dil":"tr","bayrak":"🇹🇷","kat":"kktc"},
    {"isim":"Kıbrıs Haber",     "url":"https://www.kibrishaber.org/rss",                          "dil":"tr","bayrak":"🇹🇷","kat":"kktc"},
    # ─── Güney Kıbrıs ───
    {"isim":"Cyprus Mail",      "url":"https://cyprus-mail.com/feed/",                            "dil":"en","bayrak":"🇨🇾","kat":"kibris"},
    {"isim":"Cyprus Times",     "url":"https://www.cyprustimes.com/feed/",                        "dil":"en","bayrak":"🇨🇾","kat":"kibris"},
    {"isim":"Famagusta Gazette","url":"https://famagusta-gazette.com/feed/",                      "dil":"en","bayrak":"🇨🇾","kat":"kibris"},
    # ─── İsrail / Filistin ───
    {"isim":"Times of Israel",  "url":"https://www.timesofisrael.com/feed/",                      "dil":"en","bayrak":"🇮🇱","kat":"israel"},
    {"isim":"Haaretz EN",       "url":"https://www.haaretz.com/cmlink/1.628765",                  "dil":"en","bayrak":"🇮🇱","kat":"israel"},
    {"isim":"Jerusalem Post",   "url":"https://www.jpost.com/rss/rssfeedsfrontpage.aspx",         "dil":"en","bayrak":"🇮🇱","kat":"israel"},
    {"isim":"Ynet News",        "url":"https://www.ynetnews.com/category/3082/0,7340,L-3082,00.xml","dil":"en","bayrak":"🇮🇱","kat":"israel"},
    {"isim":"Arutz Sheva",      "url":"https://www.israelnationalnews.com/rss.aspx",               "dil":"en","bayrak":"🇮🇱","kat":"israel"},
    {"isim":"i24 News",         "url":"https://www.i24news.tv/rss",                               "dil":"en","bayrak":"🇮🇱","kat":"israel"},
    {"isim":"Walla News",       "url":"https://rss.walla.co.il/feed/1",                           "dil":"he","bayrak":"🇮🇱","kat":"israel"},
    # ─── Orta Doğu Genel ───
    {"isim":"Al Jazeera EN",    "url":"https://www.aljazeera.com/xml/rss/all.xml",                "dil":"en","bayrak":"🌍","kat":"me"},
    {"isim":"Al Jazeera AR",    "url":"https://www.aljazeera.net/xml/rss/all.xml",                "dil":"ar","bayrak":"🌍","kat":"me"},
    {"isim":"Middle East Eye",  "url":"https://www.middleeasteye.net/rss",                        "dil":"en","bayrak":"🌍","kat":"me"},
    {"isim":"Arab News",        "url":"https://www.arabnews.com/rss.xml",                         "dil":"en","bayrak":"🌍","kat":"me"},
    {"isim":"Al-Monitor",       "url":"https://www.al-monitor.com/rss",                           "dil":"en","bayrak":"🌍","kat":"me"},
    {"isim":"Kurdistan24",      "url":"https://www.kurdistan24.net/en/rss",                       "dil":"en","bayrak":"🌍","kat":"me"},
    {"isim":"Rudaw EN",         "url":"https://www.rudaw.net/english/rss",                        "dil":"en","bayrak":"🌍","kat":"me"},
    {"isim":"The National UAE", "url":"https://www.thenationalnews.com/rss",                      "dil":"en","bayrak":"🇦🇪","kat":"me"},
    {"isim":"Gulf News",        "url":"https://gulfnews.com/rss/uaehomepage",                     "dil":"en","bayrak":"🇦🇪","kat":"me"},
    {"isim":"Iran International","url":"https://www.iranintl.com/en/rss",                         "dil":"en","bayrak":"🇮🇷","kat":"me"},
    {"isim":"IranWire",         "url":"https://iranwire.com/en/rss/",                             "dil":"en","bayrak":"🇮🇷","kat":"me"},
    {"isim":"PressTV",          "url":"https://www.presstv.ir/rss",                               "dil":"en","bayrak":"🇮🇷","kat":"me"},
    {"isim":"Yemen Observer",   "url":"https://www.yemenobserver.net/feed/",                      "dil":"en","bayrak":"🌍","kat":"me"},
    {"isim":"Asharq Al-Awsat",  "url":"https://english.aawsat.com/rss",                           "dil":"en","bayrak":"🌍","kat":"me"},
    {"isim":"Lebanon Daily Star","url":"https://www.dailystar.com.lb/rss/",                       "dil":"en","bayrak":"🇱🇧","kat":"me"},
    {"isim":"Naharnet",         "url":"https://www.naharnet.com/stories/rss.xml",                 "dil":"en","bayrak":"🇱🇧","kat":"me"},
    {"isim":"Al Arabiya EN",    "url":"https://english.alarabiya.net/rss",                        "dil":"en","bayrak":"🌍","kat":"me"},
    # ─── ABD / Batı ───
    {"isim":"AP Top News",      "url":"https://rsshub.app/apnews/topics/apf-intlnews",            "dil":"en","bayrak":"🇺🇸","kat":"us"},
    {"isim":"Reuters World",    "url":"https://feeds.reuters.com/Reuters/worldNews",              "dil":"en","bayrak":"🇺🇸","kat":"us"},
    {"isim":"Reuters Top",      "url":"https://feeds.reuters.com/reuters/topNews",                "dil":"en","bayrak":"🇺🇸","kat":"us"},
    {"isim":"NYT World",        "url":"https://rss.nytimes.com/services/xml/rss/nyt/World.xml",   "dil":"en","bayrak":"🇺🇸","kat":"us"},
    {"isim":"Washington Post",  "url":"https://feeds.washingtonpost.com/rss/world",               "dil":"en","bayrak":"🇺🇸","kat":"us"},
    {"isim":"The Hill",         "url":"https://thehill.com/news/feed/",                           "dil":"en","bayrak":"🇺🇸","kat":"us"},
    {"isim":"Politico",         "url":"https://www.politico.com/rss/politics08.xml",              "dil":"en","bayrak":"🇺🇸","kat":"us"},
    {"isim":"BBC World",        "url":"http://feeds.bbci.co.uk/news/world/rss.xml",               "dil":"en","bayrak":"🇬🇧","kat":"us"},
    {"isim":"The Guardian World","url":"https://www.theguardian.com/world/rss",                   "dil":"en","bayrak":"🇬🇧","kat":"us"},
    {"isim":"France 24 EN",     "url":"https://www.france24.com/en/rss",                          "dil":"en","bayrak":"🇫🇷","kat":"us"},
    {"isim":"DW World",         "url":"https://rss.dw.com/rdf/rss-en-all",                        "dil":"en","bayrak":"🇩🇪","kat":"us"},
    {"isim":"Euronews",         "url":"https://www.euronews.com/rss?format=mrss&level=theme&name=news","dil":"en","bayrak":"🇪🇺","kat":"us"},
    {"isim":"VOA News",         "url":"https://www.voanews.com/api/z-myqpz$ovkq/feed.rss",        "dil":"en","bayrak":"🇺🇸","kat":"us"},
    {"isim":"RFE/RL",           "url":"https://www.rferl.org/api/zpqutiuz-vvur/feed.rss",         "dil":"en","bayrak":"🌍","kat":"us"},
    # ─── Ukrayna / Rusya ───
    {"isim":"Kyiv Independent", "url":"https://kyivindependent.com/feed/",                        "dil":"en","bayrak":"🇺🇦","kat":"ua"},
    {"isim":"Ukrinform",        "url":"https://www.ukrinform.net/rss/block-lastnews",             "dil":"en","bayrak":"🇺🇦","kat":"ua"},
    {"isim":"Ukrainska Pravda", "url":"https://www.pravda.com.ua/eng/rss/",                       "dil":"en","bayrak":"🇺🇦","kat":"ua"},
    {"isim":"UA Wire",          "url":"https://uawire.org/feed",                                  "dil":"en","bayrak":"🇺🇦","kat":"ua"},
    {"isim":"Meduza EN",        "url":"https://meduza.io/rss/all",                                "dil":"ru","bayrak":"🇷🇺","kat":"ru"},
    {"isim":"Moscow Times",     "url":"https://www.themoscowtimes.com/rss/all",                   "dil":"en","bayrak":"🇷🇺","kat":"ru"},
    {"isim":"Novaya Gazeta",    "url":"https://novayagazeta.eu/rss",                              "dil":"ru","bayrak":"🇷🇺","kat":"ru"},
    # ─── Asya-Pasifik ───
    {"isim":"SCMP Asia",        "url":"https://www.scmp.com/rss/91/feed",                         "dil":"en","bayrak":"🇨🇳","kat":"asia"},
    {"isim":"The Hindu Intl",   "url":"https://www.thehindu.com/news/international/feeder/default.rss","dil":"en","bayrak":"🇮🇳","kat":"asia"},
    {"isim":"Dawn Pakistan",    "url":"https://www.dawn.com/feeds/home",                          "dil":"en","bayrak":"🇵🇰","kat":"asia"},
    {"isim":"NHK World",        "url":"https://www3.nhk.or.jp/nhkworld/en/news/rss/",             "dil":"en","bayrak":"🇯🇵","kat":"asia"},
    {"isim":"Korea Herald",     "url":"https://www.koreaherald.com/rss_xml/new_daily.xml",        "dil":"en","bayrak":"🇰🇷","kat":"asia"},
    {"isim":"Nikkei Asia",      "url":"https://asia.nikkei.com/rss/feed/nar",                     "dil":"en","bayrak":"🇯🇵","kat":"asia"},
    {"isim":"The Irrawaddy",    "url":"https://www.irrawaddy.com/feed",                           "dil":"en","bayrak":"🌏","kat":"asia"},
    {"isim":"RFA",              "url":"https://www.rfa.org/english/rss2.xml",                     "dil":"en","bayrak":"🌏","kat":"asia"},
    {"isim":"NDTV India",       "url":"https://feeds.feedburner.com/ndtvnews-top-stories",        "dil":"en","bayrak":"🇮🇳","kat":"asia"},
    {"isim":"The Wire India",   "url":"https://thewire.in/rss/feed",                             "dil":"en","bayrak":"🇮🇳","kat":"asia"},
    {"isim":"Vietnam News",     "url":"https://vietnamnews.vn/rss/latest-news.rss",              "dil":"en","bayrak":"🇻🇳","kat":"asia"},
    {"isim":"Bangkok Post",     "url":"https://www.bangkokpost.com/rss/data/topstories.xml",      "dil":"en","bayrak":"🇹🇭","kat":"asia"},
    {"isim":"CGTN",             "url":"https://www.cgtn.com/subscribe/rss/section/world.xml",     "dil":"en","bayrak":"🇨🇳","kat":"asia"},
    # ─── Çatışma / OSINT ───
    {"isim":"Bellingcat",       "url":"https://www.bellingcat.com/feed/",                         "dil":"en","bayrak":"🔍","kat":"osint"},
    {"isim":"The War Zone",     "url":"https://www.thedrive.com/the-war-zone/rss",                "dil":"en","bayrak":"⚔","kat":"osint"},
    {"isim":"Defense One",      "url":"https://www.defenseone.com/rss/all/",                      "dil":"en","bayrak":"⚔","kat":"osint"},
    {"isim":"ReliefWeb",        "url":"https://reliefweb.int/updates/rss.xml",                    "dil":"en","bayrak":"🌍","kat":"osint"},
    {"isim":"ACLED",            "url":"https://acleddata.com/feed/",                              "dil":"en","bayrak":"🌍","kat":"osint"},
    {"isim":"ISW",              "url":"https://www.understandingwar.org/rss",                     "dil":"en","bayrak":"⚔","kat":"osint"},
    {"isim":"Janes",            "url":"https://www.janes.com/feeds/news",                         "dil":"en","bayrak":"⚔","kat":"osint"},
    {"isim":"War on the Rocks", "url":"https://warontherocks.com/feed/",                          "dil":"en","bayrak":"⚔","kat":"osint"},
    # ─── İnsani / BM ───
    {"isim":"UN News ME",       "url":"https://news.un.org/feed/subscribe/en/news/region/middle-east/feed/rss.xml","dil":"en","bayrak":"🌍","kat":"un"},
    {"isim":"UNHCR",            "url":"https://www.unhcr.org/news/rss.xml",                       "dil":"en","bayrak":"🌍","kat":"un"},
    {"isim":"Amnesty Intl",     "url":"https://www.amnesty.org/en/feed/",                         "dil":"en","bayrak":"🌍","kat":"un"},
    {"isim":"HRW",              "url":"https://www.hrw.org/rss",                                  "dil":"en","bayrak":"🌍","kat":"un"},
    {"isim":"OCHA",             "url":"https://www.unocha.org/rss.xml",                           "dil":"en","bayrak":"🌍","kat":"un"},
    # ─── Reddit ───
    {"isim":"r/worldnews",      "url":"https://www.reddit.com/r/worldnews/.rss?limit=8",          "dil":"en","bayrak":"🌐","kat":"reddit"},
    {"isim":"r/geopolitics",    "url":"https://www.reddit.com/r/geopolitics/.rss?limit=8",        "dil":"en","bayrak":"🌐","kat":"reddit"},
    {"isim":"r/turkey",         "url":"https://www.reddit.com/r/turkey/.rss?limit=8",             "dil":"en","bayrak":"🇹🇷","kat":"reddit"},
    {"isim":"r/ukraine",        "url":"https://www.reddit.com/r/ukraine/.rss?limit=8",            "dil":"en","bayrak":"🇺🇦","kat":"reddit"},
    {"isim":"r/MiddleEast",     "url":"https://www.reddit.com/r/MiddleEast/.rss?limit=8",         "dil":"en","bayrak":"🌍","kat":"reddit"},
    {"isim":"r/syriancivilwar", "url":"https://www.reddit.com/r/syriancivilwar/.rss?limit=8",     "dil":"en","bayrak":"🌍","kat":"reddit"},
    {"isim":"r/IsraelPalestine","url":"https://www.reddit.com/r/IsraelPalestine/.rss?limit=8",    "dil":"en","bayrak":"🌍","kat":"reddit"},
    {"isim":"r/UkraineWarVideo","url":"https://www.reddit.com/r/UkraineWarVideoReport/.rss?limit=8","dil":"en","bayrak":"🇺🇦","kat":"reddit"},
    {"isim":"r/iran",           "url":"https://www.reddit.com/r/iran/.rss?limit=8",               "dil":"en","bayrak":"🇮🇷","kat":"reddit"},
    {"isim":"r/China",          "url":"https://www.reddit.com/r/China/.rss?limit=8",              "dil":"en","bayrak":"🇨🇳","kat":"reddit"},
    {"isim":"r/pakistan",       "url":"https://www.reddit.com/r/pakistan/.rss?limit=8",           "dil":"en","bayrak":"🇵🇰","kat":"reddit"},
    {"isim":"r/AskMiddleEast",  "url":"https://www.reddit.com/r/AskMiddleEast/.rss?limit=8",      "dil":"en","bayrak":"🌍","kat":"reddit"},
    # ─── Afrika ───
    {"isim":"AllAfrica",        "url":"https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf","dil":"en","bayrak":"🌍","kat":"africa"},
    {"isim":"The East African", "url":"https://www.theeastafrican.co.ke/rss/1349822",             "dil":"en","bayrak":"🌍","kat":"africa"},
    {"isim":"Sudan Tribune",    "url":"https://sudantribune.com/feeds/rss",                       "dil":"en","bayrak":"🌍","kat":"africa"},
]

BAYRAKLAR = {
    "en":"🇬🇧","ru":"🇷🇺","ar":"🇵🇸","uk":"🇺🇦","fr":"🇫🇷",
    "de":"🇩🇪","tr":"🇹🇷","he":"🇮🇱","fa":"🇮🇷","es":"🇪🇸",
    "it":"🇮🇹","zh-cn":"🇨🇳","zh":"🇨🇳","ja":"🇯🇵","ko":"🇰🇷",
    "pl":"🇵🇱","cs":"🇨🇿","hu":"🇭🇺","ro":"🇷🇴","unk":"🌍",
    "pt":"🇵🇹","nl":"🇳🇱","sv":"🇸🇪","no":"🇳🇴","da":"🇩🇰",
}

YUKSEK_KELIMELER = [
    "saldırı","patlama","ölü","yaralı","füze","bomba","savaş","operasyon","çatışma",
    "attack","explosion","killed","wounded","missile","bomb","war","operation","clash",
    "breaking","urgent","acil","son dakika","airstrike","rocket","shelling","offensive",
    "arrested","detained","fire","blaze","crisis","shooting","gunfire","stabbing",
]
KRITIK_KELIMELER = [
    "nükleer","kimyasal","biyolojik","katliam","darbe","soykırım",
    "nuclear","chemical","biological","massacre","genocide","coup",
    "mass casualty","toplu","ceasefire","ateşkes","withdrawal","çekilme",
    "hostage","rehineli","terror alert","kırmızı alarm",
]

# ══════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════
gecmis_hash: deque = deque(maxlen=3000)
sse_clients: List[asyncio.Queue] = []
son_veri_cache = None
scheduler: Optional[AsyncIOScheduler] = None
rss_idx = tg_idx = nt_idx = tw_sayac = gdelt_sayac = 0

# ══════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════
async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        # Tablo oluştur (ilk kurulum)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS haberler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE NOT NULL,
                kaynak TEXT, kaynak_tip TEXT, kaynak_kat TEXT,
                mesaj_orijinal TEXT, mesaj_ceviri TEXT,
                dil_kodu TEXT, bayrak TEXT,
                ai_tespit INTEGER DEFAULT 0,
                koordinat TEXT, hedef_isim TEXT,
                link TEXT, oncelik INTEGER DEFAULT 0,
                oncelik_etiket TEXT, zaman TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: eski DB'de eksik olabilecek kolonları ekle
        existing = await db.execute("PRAGMA table_info(haberler)")
        cols = {row[1] async for row in existing}
        migrations = {
            "kaynak_kat":     "ALTER TABLE haberler ADD COLUMN kaynak_kat TEXT DEFAULT ''",
            "oncelik":        "ALTER TABLE haberler ADD COLUMN oncelik INTEGER DEFAULT 0",
            "oncelik_etiket": "ALTER TABLE haberler ADD COLUMN oncelik_etiket TEXT DEFAULT 'DÜŞÜK'",
            "koordinat":      "ALTER TABLE haberler ADD COLUMN koordinat TEXT",
            "hedef_isim":     "ALTER TABLE haberler ADD COLUMN hedef_isim TEXT DEFAULT ''",
            "ai_tespit":      "ALTER TABLE haberler ADD COLUMN ai_tespit INTEGER DEFAULT 0",
            "link":           "ALTER TABLE haberler ADD COLUMN link TEXT DEFAULT ''",
        }
        for col, sql in migrations.items():
            if col not in cols:
                try:
                    await db.execute(sql)
                    logger.info("🔧 Migration: +%s kolonu eklendi", col)
                except Exception as e:
                    logger.warning("Migration %s: %s", col, e)
        for idx in ["hash","created_at DESC","kaynak_tip","oncelik"]:
            col = idx.split()[0]
            await db.execute(f"CREATE INDEX IF NOT EXISTS idx_{col} ON haberler({idx})")
        await db.commit()
    logger.info("✅ DB hazır — %s", DB_PATH)

async def db_kaydet(v: dict) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR IGNORE INTO haberler
                (hash,kaynak,kaynak_tip,kaynak_kat,mesaj_orijinal,mesaj_ceviri,
                 dil_kodu,bayrak,ai_tespit,koordinat,hedef_isim,link,oncelik,oncelik_etiket,zaman)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (v["hash"],v["kaynak"],v["kaynak_tip"],v.get("kaynak_kat",""),
                  v["mesaj_orijinal"],v["mesaj_ceviri"],v["dil_kodu"],v["bayrak"],
                  1 if v["ai_tespit"] else 0,
                  json.dumps(v["koordinat"]) if v["koordinat"] else None,
                  v["hedef_isim"],v["link"],v["oncelik"],v["oncelik_etiket"],v["zaman"]))
            chg = db.total_changes
            await db.commit()
            await db.execute(f"DELETE FROM haberler WHERE id NOT IN (SELECT id FROM haberler ORDER BY created_at DESC LIMIT {MAX_DB_ROWS})")
            await db.commit()
            return chg > 0
    except Exception as e:
        logger.error("DB: %s", e); return False

async def db_listele(limit=50, offset=0, tip="all", arama="", alarm=False, kat="") -> list:
    cond, params = [], []
    if tip not in ("all",""): cond.append("kaynak_tip=?"); params.append(tip)
    if alarm: cond.append("ai_tespit=1")
    if kat:   cond.append("kaynak_kat=?"); params.append(kat)
    if arama:
        cond.append("(mesaj_ceviri LIKE ? OR mesaj_orijinal LIKE ? OR kaynak LIKE ?)")
        params += [f"%{arama}%"]*3
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    params += [limit, offset]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"SELECT * FROM haberler {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params) as cur:
            rows = await cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("koordinat"): d["koordinat"] = json.loads(d["koordinat"])
                result.append(d)
            return result

async def db_saydir() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async def cnt(q): return (await (await db.execute(q)).fetchone())[0]
        return {
            "toplam": await cnt("SELECT COUNT(*) FROM haberler"),
            "alarm":  await cnt("SELECT COUNT(*) FROM haberler WHERE ai_tespit=1"),
            "twitter":await cnt("SELECT COUNT(*) FROM haberler WHERE kaynak_tip='twitter'"),
            "rss":    await cnt("SELECT COUNT(*) FROM haberler WHERE kaynak_tip='rss'"),
            "tg":     await cnt("SELECT COUNT(*) FROM haberler WHERE kaynak_tip='tg'"),
        }

# ══════════════════════════════════════════════
# YARDIMCILAR
# ══════════════════════════════════════════════
def hash_olustur(t: str) -> str:
    return hashlib.md5(t.strip().lower().encode()).hexdigest()

def oncelik_hesapla(metin: str, ai: bool) -> tuple:
    skor, t = 0, metin.lower()
    if ai: skor += 50
    for k in KRITIK_KELIMELER:
        if k.lower() in t: skor += 40; break
    for k in YUKSEK_KELIMELER:
        if k.lower() in t: skor += 20; break
    if skor >= 80: return skor, "KRİTİK"
    if skor >= 50: return skor, "YÜKSEK"
    if skor >= 20: return skor, "ORTA"
    return skor, "DÜŞÜK"

def dil_cevir(metin: str) -> tuple:
    if not metin or len(metin.strip()) < 5: return "unk", metin
    try:    dil = detect(metin)
    except: dil = "unk"
    if dil == "tr": return "tr", metin
    try:    return dil, GoogleTranslator(source="auto", target="tr").translate(metin[:500]) or metin
    except: return dil, metin

def lokasyon_tara(metin: str) -> tuple:
    t = metin.lower()
    for lok, koord in KRITIK_LOKASYONLAR.items():
        if lok.lower() in t: return True, koord, lok.upper()
    return False, None, ""

def paket(kaynak, orijinal, ceviri, dil, bayrak, tip="rss", link="", kat="") -> dict:
    ai, koord, hedef = lokasyon_tara(orijinal + " " + ceviri)
    onc, onc_et = oncelik_hesapla(orijinal + " " + ceviri, ai)
    return {
        "hash": hash_olustur(orijinal), "kaynak": kaynak,
        "mesaj_ceviri": ceviri, "mesaj_orijinal": orijinal,
        "dil_kodu": dil.upper(), "bayrak": bayrak,
        "zaman": datetime.now().strftime("%H:%M:%S"),
        "ai_tespit": ai, "koordinat": koord, "hedef_isim": hedef,
        "kaynak_tip": tip, "kaynak_kat": kat, "link": link,
        "oncelik": onc, "oncelik_etiket": onc_et,
    }

# ══════════════════════════════════════════════
# SSE
# ══════════════════════════════════════════════
async def sse_yayinla(veri: dict):
    global son_veri_cache
    son_veri_cache = veri
    for q in list(sse_clients):
        try:   await q.put(veri)
        except: sse_clients.remove(q)

# ══════════════════════════════════════════════
# SCRAPERS
# ══════════════════════════════════════════════
async def rss_cek(k: dict) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=9.0, follow_redirects=True) as c:
            r = await c.get(k["url"], headers={
                "User-Agent":"Mozilla/5.0 (compatible; ViewMonitor/3.3)",
                "Accept":"application/rss+xml,application/xml,text/xml,*/*"})
            r.raise_for_status()
        feed = feedparser.parse(r.text)
        if not feed.entries: return None
        havuz = feed.entries[:10]; random.shuffle(havuz)
        for entry in havuz:
            baslik = entry.get("title","").strip()
            ozet   = BeautifulSoup(entry.get("summary",entry.get("description","")),"html.parser").get_text(" ",strip=True)
            link   = entry.get("link","")
            tam    = baslik + (" — " + ozet[:220] if ozet else "")
            if not tam or len(tam) < 10: continue
            h = hash_olustur(tam)
            if h in gecmis_hash: continue
            gecmis_hash.append(h)
            dil = k.get("dil","en")
            ceviri = tam if dil=="tr" else dil_cevir(tam)[1]
            return paket(k["isim"],tam,ceviri,dil,k.get("bayrak","🌍"),
                         tip="rss",link=link,kat=k.get("kat",""))
    except Exception as e:
        logger.debug("RSS [%s]: %s", k["isim"], e)
    return None

async def telegram_cek(kanal: str) -> Optional[dict]:
    sinir = datetime.now(timezone.utc) - timedelta(hours=TELEGRAM_MAX_YAS_SAAT)
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    ]
    for agent in agents:
        try:
            async with httpx.AsyncClient(timeout=9.0, follow_redirects=True) as c:
                r = await c.get(f"https://t.me/s/{kanal}",
                    headers={"User-Agent":agent,"Accept-Language":"tr-TR,tr;q=0.9,en;q=0.8"})
                if r.status_code != 200: continue
            soup = BeautifulSoup(r.text,"html.parser")
            for msg in reversed(soup.find_all("div",class_="tgme_widget_message")):
                # Zaman filtresi
                te = msg.find("time")
                if te and te.get("datetime"):
                    try:
                        mt = datetime.fromisoformat(te["datetime"].replace("Z","+00:00"))
                        if mt < sinir: continue
                    except: pass
                kutu = msg.find("div",class_="tgme_widget_message_text")
                if not kutu: continue
                metin = kutu.get_text(" ",strip=True)
                if not metin or len(metin) < 10: continue
                h = hash_olustur(metin)
                if h in gecmis_hash: continue
                gecmis_hash.append(h)
                la = msg.find("a",class_="tgme_widget_message_date")
                link = la["href"] if la and la.get("href") else f"https://t.me/{kanal}"
                dil, ceviri = dil_cevir(metin)
                return paket(f"TG/{kanal.upper()}",metin,ceviri,dil,
                             BAYRAKLAR.get(dil,"🌍"),tip="tg",link=link,kat="tg")
        except Exception as e:
            logger.debug("TG [%s]: %s", kanal, e)
    return None

async def nitter_cek(username: str) -> Optional[dict]:
    random.shuffle(NITTER_INSTANCES)
    for inst in NITTER_INSTANCES[:4]:
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as c:
                r = await c.get(f"{inst}/{username}/rss",
                    headers={"User-Agent":"Mozilla/5.0 (compatible; RSS)","Accept":"application/rss+xml"})
                if r.status_code != 200: continue
            feed = feedparser.parse(r.text)
            if not feed.entries: continue
            havuz = feed.entries[:5]; random.shuffle(havuz)
            for entry in havuz:
                metin = BeautifulSoup(entry.get("summary",entry.get("title","")),"html.parser").get_text(" ",strip=True)
                if not metin or len(metin) < 15: continue
                h = hash_olustur(metin)
                if h in gecmis_hash: continue
                gecmis_hash.append(h)
                link = entry.get("link","").replace(inst,"https://twitter.com")
                dil, ceviri = dil_cevir(metin)
                return paket(f"𝕏 @{username}",metin,ceviri,dil,
                             BAYRAKLAR.get(dil,"🌍"),tip="twitter",link=link,kat="twitter")
        except Exception as e:
            logger.debug("Nitter [%s@%s]: %s", username, inst, e)
    return None

async def gdelt_cek() -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=12.0) as c:
            r = await c.get("https://api.gdeltproject.org/api/v2/doc/doc", params={
                "query":"conflict war attack explosion missile airstrike Israel Gaza Lebanon Ukraine Russia",
                "mode":"artlist","format":"json","maxrecords":"10","timespan":"1h","sort":"datedesc"})
            if r.status_code != 200: return None
        data = r.json(); arts = data.get("articles",[]); random.shuffle(arts)
        for art in arts:
            baslik = art.get("title","").strip(); link = art.get("url","")
            kaynak = art.get("domain","GDELT")
            if not baslik or len(baslik) < 10: continue
            h = hash_olustur(baslik)
            if h in gecmis_hash: continue
            gecmis_hash.append(h)
            dil, ceviri = dil_cevir(baslik)
            return paket(f"⚔GDELT/{kaynak}",baslik,ceviri,dil,"🌍",tip="gdelt",link=link,kat="conflict")
    except Exception as e:
        logger.debug("GDELT: %s", e)
    return None

# ══════════════════════════════════════════════
# SCHEDULER
# ══════════════════════════════════════════════
async def toplu_cek():
    global rss_idx, tg_idx, nt_idx, tw_sayac, gdelt_sayac
    sonuclar = []

    # RSS — 5 kaynak paralel (asyncio.gather ile hızlandırıldı)
    rss_batch = []
    for _ in range(5):
        k = RSS_KAYNAKLARI[rss_idx % len(RSS_KAYNAKLARI)]; rss_idx += 1
        rss_batch.append(rss_cek(k))
    rss_results = await asyncio.gather(*rss_batch, return_exceptions=True)
    for v in rss_results:
        if v and not isinstance(v, Exception): sonuclar.append(v)

    # Telegram — 2 kanal paralel
    tg_batch = []
    for _ in range(2):
        k = TELEGRAM_KANALLARI[tg_idx % len(TELEGRAM_KANALLARI)]; tg_idx += 1
        tg_batch.append(telegram_cek(k))
    tg_results = await asyncio.gather(*tg_batch, return_exceptions=True)
    for v in tg_results:
        if v and not isinstance(v, Exception): sonuclar.append(v)

    # Nitter/Twitter
    hesap = NITTER_HESAPLARI[nt_idx % len(NITTER_HESAPLARI)]; nt_idx += 1
    v = await nitter_cek(hesap)
    if v: sonuclar.append(v)

    # GDELT — her 5 döngüde bir
    gdelt_sayac += 1
    if gdelt_sayac % 5 == 0:
        v = await gdelt_cek()
        if v: sonuclar.append(v)

    for veri in sonuclar:
        if await db_kaydet(veri):
            await sse_yayinla(veri)
            logger.info("[%s] %s — %s",veri["kaynak_tip"].upper(),veri["kaynak"],veri["oncelik_etiket"])

# ══════════════════════════════════════════════
# LIFESPAN
# ══════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    await db_init()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(toplu_cek,"interval",seconds=FETCH_INTERVAL)
    scheduler.start()
    logger.info("🚀 Scheduler başladı — her %dsn", FETCH_INTERVAL)
    asyncio.create_task(toplu_cek())
    yield
    scheduler.shutdown()

# ══════════════════════════════════════════════
# API
# ══════════════════════════════════════════════
app = FastAPI(title="ViewMonitor Pro API",version="3.3.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["GET","POST"],allow_headers=["*"])

@app.get("/")
def root(): return {"sistem":"ViewMonitor Pro v3.3","stream":"/api/stream","docs":"/docs"}

@app.get("/api/durum")
async def saglik():
    stats = await db_saydir()
    return {"durum":"aktif","zaman":datetime.now().isoformat(),"db":stats,
            "scheduler":scheduler.running if scheduler else False,"sse":len(sse_clients),
            "kaynaklar":{"rss":len(RSS_KAYNAKLARI),"telegram":len(TELEGRAM_KANALLARI),
                         "twitter":len(NITTER_HESAPLARI)}}

@app.get("/api/stream")
async def sse_stream(request: Request):
    queue: asyncio.Queue = asyncio.Queue()
    sse_clients.append(queue)
    async def gen() -> AsyncGenerator[str,None]:
        for h in reversed(await db_listele(limit=20)):
            yield f"data: {json.dumps(h,ensure_ascii=False,default=str)}\n\n"
        try:
            while True:
                if await request.is_disconnected(): break
                try:
                    veri = await asyncio.wait_for(queue.get(),timeout=25.0)
                    yield f"data: {json.dumps(veri,ensure_ascii=False,default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield 'data: {"ping":true}\n\n'
        finally:
            if queue in sse_clients: sse_clients.remove(queue)
    return StreamingResponse(gen(),media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","Connection":"keep-alive",
                 "X-Accel-Buffering":"no","Access-Control-Allow-Origin":"*"})

@app.get("/api/haberler")
async def haberler(limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0),
                   tip:str=Query("all"),arama:str=Query(""),alarm:bool=Query(False),kat:str=Query("")):
    data = await db_listele(limit=limit,offset=offset,tip=tip,arama=arama,alarm=alarm,kat=kat)
    stats = await db_saydir()
    return {"haberler":data,"istatistik":stats,"limit":limit,"offset":offset}

@app.get("/api/ara")
async def ara(q:str=Query(...,min_length=2)):
    data = await db_listele(limit=200,arama=q)
    return {"sonuclar":data,"adet":len(data),"sorgu":q}

@app.get("/api/export")
async def export(format:str=Query("json"),tip:str=Query("all"),limit:int=Query(1000)):
    data = await db_listele(limit=limit,tip=tip)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    if format=="csv":
        buf = io.StringIO()
        if data:
            w = csv.DictWriter(buf,fieldnames=data[0].keys())
            w.writeheader(); w.writerows(data)
        return StreamingResponse(iter([buf.getvalue()]),media_type="text/csv",
            headers={"Content-Disposition":f"attachment; filename=viewmonitor_{ts}.csv"})
    content = json.dumps({"haberler":data,"export_zaman":datetime.now().isoformat()},ensure_ascii=False,indent=2)
    return StreamingResponse(iter([content]),media_type="application/json",
        headers={"Content-Disposition":f"attachment; filename=viewmonitor_{ts}.json"})

@app.get("/api/lokasyonlar")
def lokasyonlar():
    return {"lokasyonlar":{k:{"koordinat":v} for k,v in KRITIK_LOKASYONLAR.items()}}

@app.get("/api/kaynaklar")
def kaynaklar():
    return {"rss":len(RSS_KAYNAKLARI),"telegram":len(TELEGRAM_KANALLARI),
            "twitter":len(NITTER_HESAPLARI),"liste_rss":RSS_KAYNAKLARI}

@app.post("/api/tetikle")
async def tetikle():
    asyncio.create_task(toplu_cek())
    return {"mesaj":"Veri çekimi tetiklendi"}

if __name__ == "__main__":
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]; s.close()
    except:
        local_ip = "?.?.?.?"
    print(f"""
╔══════════════════════════════════════════════╗
║  ViewMonitor Pro API v3.3                    ║
║                                              ║
║  Yerel :  http://127.0.0.1:8080              ║
║  Ağ    :  http://{local_ip}:8080             ║
║                                              ║
║  Docs  :  http://127.0.0.1:8080/docs         ║
║  Stream:  http://127.0.0.1:8080/api/stream   ║
╚══════════════════════════════════════════════╝
    """)
    import os
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
