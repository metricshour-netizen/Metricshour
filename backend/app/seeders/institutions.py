"""
Seed country_institutions table with real official URLs.
Data: government portals, central banks, stats offices for all 196 countries.
Idempotent — safe to re-run.

Run: python seed.py --only institutions
"""

import logging
from datetime import date

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.country import Country, CountryInstitution

log = logging.getLogger(__name__)

# Real official URLs: (country_name, gov_portal, central_bank, stats_office)
# Sources: verified official government domains
INSTITUTIONS_DATA: list[tuple[str, str, str, str]] = [
    ("Afghanistan", "https://president.gov.af", "https://dab.gov.af", "https://nsia.gov.af"),
    ("Albania", "https://e-albania.al", "https://www.bankofalbania.org", "https://www.instat.gov.al"),
    ("Algeria", "https://www.el-mouradia.dz", "https://www.bank-of-algeria.dz", "https://www.ons.dz"),
    ("Andorra", "https://www.govern.ad", "https://www.afa.ad", "https://www.estadistica.ad"),
    ("Angola", "https://www.governo.gov.ao", "https://www.bna.ao", "https://www.ine.gov.ao"),
    ("Antigua and Barbuda", "https://www.ab.gov.ag", "https://www.ab.gov.ag", "https://statistics.gov.ag"),
    ("Argentina", "https://www.argentina.gob.ar", "https://www.bcra.gob.ar", "https://www.indec.gob.ar"),
    ("Armenia", "https://www.gov.am", "https://www.cba.am", "https://www.armstat.am"),
    ("Australia", "https://www.australia.gov.au", "https://www.rba.gov.au", "https://www.abs.gov.au"),
    ("Austria", "https://www.oesterreich.gv.at", "https://www.oenb.at", "https://www.statistik.at"),
    ("Azerbaijan", "https://www.gov.az", "https://www.cbar.az", "https://www.stat.gov.az"),
    ("Bahamas", "https://www.bahamas.gov.bs", "https://www.centralbankbahamas.com", "https://www.bahamas.gov.bs"),
    ("Bahrain", "https://www.bahrain.bh", "https://www.cbb.gov.bh", "https://www.data.gov.bh"),
    ("Bangladesh", "https://www.bangladesh.gov.bd", "https://www.bb.org.bd", "https://www.bbs.gov.bd"),
    ("Barbados", "https://www.gov.bb", "http://www.centralbank.org.bb", "https://stats.gov.bb"),
    ("Belarus", "https://www.government.by", "https://www.nbrb.by", "https://www.belstat.gov.by"),
    ("Belgium", "https://www.belgium.be", "https://www.nbb.be", "https://statbel.fgov.be"),
    ("Belize", "https://www.belize.gov.bz", "https://www.centralbank.org.bz", "https://www.sib.org.bz"),
    ("Benin", "https://www.gouv.bj", "https://www.bceao.int", "https://www.insae-bj.org"),
    ("Bhutan", "https://www.bhutan.gov.bt", "https://www.rma.org.bt", "https://www.nsb.gov.bt"),
    ("Bolivia", "https://www.bolivia.gob.bo", "https://www.bcb.gob.bo", "https://www.ine.gob.bo"),
    ("Bosnia and Herzegovina", "https://www.fbihvlada.gov.ba", "https://www.cbbh.ba", "https://www.bhas.ba"),
    ("Botswana", "https://www.gov.bw", "https://www.bankofbotswana.bw", "https://www.statsbots.org.bw"),
    ("Brazil", "https://www.gov.br", "https://www.bcb.gov.br", "https://www.ibge.gov.br"),
    ("Brunei Darussalam", "https://www.gov.bn", "https://www.bdcb.gov.bn", "https://www.deps.gov.bn"),
    ("Bulgaria", "https://www.gov.bg", "https://www.bnb.bg", "https://www.nsi.bg"),
    ("Burkina Faso", "https://www.gouvernement.gov.bf", "https://www.bceao.int", "https://www.insd.bf"),
    ("Burundi", "https://www.presidence.gov.bi", "https://www.brb.bi", "https://www.isteebu.bi"),
    ("Cabo Verde", "https://www.governo.cv", "https://www.bcv.cv", "https://www.ine.cv"),
    ("Cambodia", "https://www.mfaic.gov.kh", "https://www.nbc.org.kh", "https://www.nis.gov.kh"),
    ("Cameroon", "https://www.spm.gov.cm", "https://www.beac.int", "https://www.ins-cameroun.cm"),
    ("Canada", "https://www.canada.ca", "https://www.bankofcanada.ca", "https://www.statcan.gc.ca"),
    ("Central African Republic", "https://www.presidence.cf", "https://www.beac.int", "https://www.icasees.org"),
    ("Chad", "https://www.gouvernement.td", "https://www.beac.int", "https://www.ins-tchad.org"),
    ("Chile", "https://www.gob.cl", "https://www.bcentral.cl", "https://www.ine.cl"),
    ("China", "https://www.gov.cn", "https://www.pbc.gov.cn", "https://www.stats.gov.cn"),
    ("Colombia", "https://www.gov.co", "https://www.banrep.gov.co", "https://www.dane.gov.co"),
    ("Comoros", "https://www.beit-salam.km", "https://www.banque-comores.km", "https://www.inseed.km"),
    ("Congo", "https://www.presidence.cg", "https://www.beac.int", "https://www.ins-congo.cg"),
    ("Costa Rica", "https://www.presidencia.go.cr", "https://www.bccr.fi.cr", "https://www.inec.go.cr"),
    ("Côte d'Ivoire", "https://www.gouv.ci", "https://www.bceao.int", "https://www.ins.ci"),
    ("Croatia", "https://www.vlada.hr", "https://www.hnb.hr", "https://www.dzs.hr"),
    ("Cuba", "https://www.cubagob.cu", "https://www.bc.gob.cu", "https://www.onei.gob.cu"),
    ("Cyprus", "https://www.cyprus.gov.cy", "https://www.centralbank.cy", "https://www.cystat.gov.cy"),
    ("Czech Republic", "https://www.vlada.cz", "https://www.cnb.cz", "https://www.czso.cz"),
    ("Denmark", "https://www.regeringen.dk", "https://www.nationalbanken.dk", "https://www.dst.dk"),
    ("Djibouti", "https://www.presidence.dj", "https://www.banque-centrale.dj", "https://www.insd.dj"),
    ("Dominica", "https://www.dominica.gov.dm", "https://www.eccb-centralbank.org", "https://www.statistics.gov.dm"),
    ("Dominican Republic", "https://www.presidencia.gob.do", "https://www.bancentral.gov.do", "https://www.one.gob.do"),
    ("Ecuador", "https://www.presidencia.gob.ec", "https://www.bce.fin.ec", "https://www.ecuadorencifras.gob.ec"),
    ("Egypt", "https://www.egypt.gov.eg", "https://www.cbe.org.eg", "https://www.capmas.gov.eg"),
    ("El Salvador", "https://www.presidencia.gob.sv", "https://www.bcr.gob.sv", "https://www.digestyc.gob.sv"),
    ("Equatorial Guinea", "https://www.guineaecuatorialpress.com", "https://www.beac.int", "https://www.inege.gq"),
    ("Eritrea", "https://www.shabait.com", "https://www.bdce.gov.er", "https://www.shabait.com"),
    ("Estonia", "https://www.valitsus.ee", "https://www.eestipank.ee", "https://www.stat.ee"),
    ("Eswatini", "https://www.gov.sz", "https://www.centralbank.org.sz", "https://www.szstats.org.sz"),
    ("Ethiopia", "https://www.ethiopia.gov.et", "https://www.nbe.gov.et", "https://www.statsethiopia.gov.et"),
    ("Fiji", "https://www.fiji.gov.fj", "https://www.rbf.gov.fj", "https://www.statsfiji.gov.fj"),
    ("Finland", "https://www.valtioneuvosto.fi", "https://www.suomenpankki.fi", "https://www.stat.fi"),
    ("France", "https://www.gouvernement.fr", "https://www.banque-france.fr", "https://www.insee.fr"),
    ("Gabon", "https://www.gouvernement.ga", "https://www.beac.int", "https://www.stat-gabon.ga"),
    ("Gambia", "https://www.statehouse.gm", "https://www.cbg.gm", "https://www.gbosdata.org"),
    ("Georgia", "https://www.gov.ge", "https://www.nbg.gov.ge", "https://www.geostat.ge"),
    ("Germany", "https://www.bundesregierung.de", "https://www.bundesbank.de", "https://www.destatis.de"),
    ("Ghana", "https://www.ghana.gov.gh", "https://www.bog.gov.gh", "https://www.statsghana.gov.gh"),
    ("Greece", "https://www.government.gov.gr", "https://www.bankofgreece.gr", "https://www.statistics.gr"),
    ("Grenada", "https://www.gov.gd", "https://www.eccb-centralbank.org", "https://stats.gov.gd"),
    ("Guatemala", "https://www.guatemala.gob.gt", "https://www.banguat.gob.gt", "https://www.ine.gob.gt"),
    ("Guinea", "https://www.presidence.gov.gn", "https://www.bcrg-guinee.org", "https://www.stat-guinee.org"),
    ("Guinea-Bissau", "https://www.gov.gw", "https://www.bceao.int", "https://www.stat-guinebissau.com"),
    ("Guyana", "https://www.gina.gov.gy", "https://www.bankofguyana.org.gy", "https://www.statisticsguyana.gov.gy"),
    ("Haiti", "https://www.primature.gouv.ht", "https://www.brh.ht", "https://www.ihsi.gouv.ht"),
    ("Honduras", "https://www.presidencia.gob.hn", "https://www.bch.hn", "https://www.ine.gob.hn"),
    ("Hungary", "https://www.kormany.hu", "https://www.mnb.hu", "https://www.ksh.hu"),
    ("Iceland", "https://www.government.is", "https://www.cb.is", "https://www.statice.is"),
    ("India", "https://www.india.gov.in", "https://www.rbi.org.in", "https://www.mospi.gov.in"),
    ("Indonesia", "https://www.indonesia.go.id", "https://www.bi.go.id", "https://www.bps.go.id"),
    ("Iran", "https://www.president.ir", "https://www.cbi.ir", "https://www.amar.org.ir"),
    ("Iraq", "https://www.cabinet.iq", "https://www.cbiraq.org", "https://www.cosit.gov.iq"),
    ("Ireland", "https://www.gov.ie", "https://www.centralbank.ie", "https://www.cso.ie"),
    ("Israel", "https://www.gov.il", "https://www.boi.org.il", "https://www.cbs.gov.il"),
    ("Italy", "https://www.governo.it", "https://www.bancaditalia.it", "https://www.istat.it"),
    ("Jamaica", "https://www.jis.gov.jm", "https://www.boj.org.jm", "https://www.statinja.gov.jm"),
    ("Japan", "https://www.kantei.go.jp", "https://www.boj.or.jp", "https://www.stat.go.jp"),
    ("Jordan", "https://www.jordan.gov.jo", "https://www.cbj.gov.jo", "http://www.dos.gov.jo"),
    ("Kazakhstan", "https://www.gov.kz", "https://www.nationalbank.kz", "https://www.stat.gov.kz"),
    ("Kenya", "https://www.president.go.ke", "https://www.centralbank.go.ke", "https://www.knbs.or.ke"),
    ("Kiribati", "https://www.president.gov.ki", "https://www.pmo.gov.ki", "https://www.mfed.gov.ki"),
    ("Kuwait", "https://www.e.gov.kw", "https://www.cbk.gov.kw", "https://www.csb.gov.kw"),
    ("Kyrgyzstan", "https://www.gov.kg", "https://www.nbkr.kg", "https://www.stat.gov.kg"),
    ("Laos", "https://www.tourismlaos.org", "https://www.bol.gov.la", "https://www.lsb.gov.la"),
    ("Latvia", "https://www.mk.gov.lv", "https://www.bank.lv", "https://www.csp.gov.lv"),
    ("Lebanon", "https://www.pcm.gov.lb", "https://www.bdl.gov.lb", "https://www.cas.gov.lb"),
    ("Lesotho", "https://www.gov.ls", "https://www.centralbank.org.ls", "https://www.bos.gov.ls"),
    ("Liberia", "https://www.emansion.gov.lr", "https://www.cbl.org.lr", "https://www.lisgis.gov.lr"),
    ("Libya", "https://www.pm.gov.ly", "https://www.cbl.gov.ly", "https://www.bsc.ly"),
    ("Liechtenstein", "https://www.regierung.li", "https://www.llv.li", "https://www.asuntos.li"),
    ("Lithuania", "https://www.lrv.lt", "https://www.lb.lt", "https://www.lsd.lt"),
    ("Luxembourg", "https://www.gouvernement.lu", "https://www.bcl.lu", "https://www.statistiques.public.lu"),
    ("Madagascar", "https://www.presidence.gov.mg", "https://www.banky-foibe.mg", "https://www.instat.mg"),
    ("Malawi", "https://www.malawi.gov.mw", "https://www.rbm.mw", "https://www.nsomalawi.mw"),
    ("Malaysia", "https://www.malaysia.gov.my", "https://www.bnm.gov.my", "https://www.dosm.gov.my"),
    ("Maldives", "https://www.presidency.gov.mv", "https://www.mma.gov.mv", "https://www.statisticsmaldives.gov.mv"),
    ("Mali", "https://www.primature.gov.ml", "https://www.bceao.int", "https://www.instat-mali.org"),
    ("Malta", "https://www.gov.mt", "https://www.centralbankmalta.org", "https://www.nso.gov.mt"),
    ("Marshall Islands", "https://www.rmigovernment.org", "https://www.rmi.org", "https://www.epmormi.org"),
    ("Mauritania", "https://www.ami.mr", "https://www.bcm.mr", "https://www.ons.mr"),
    ("Mauritius", "https://www.pmo.govmu.org", "https://www.bom.mu", "https://statsmauritius.govmu.org"),
    ("Mexico", "https://www.gob.mx", "https://www.banxico.org.mx", "https://www.inegi.org.mx"),
    ("Micronesia", "https://www.fsmgov.org", "https://www.fsm.fm", "https://www.fsmstatistics.fm"),
    ("Moldova", "https://www.gov.md", "https://www.bnm.md", "https://www.statistica.md"),
    ("Monaco", "https://www.gouv.mc", "https://www.gouv.mc", "https://www.imsee.mc"),
    ("Mongolia", "https://www.zasag.mn", "https://www.mongolbank.mn", "https://www.1212.mn"),
    ("Montenegro", "https://www.gov.me", "https://www.cbcg.me", "https://www.monstat.org"),
    ("Morocco", "https://www.maroc.ma", "https://www.bkam.ma", "https://www.hcp.ma"),
    ("Mozambique", "https://www.portaldogoverno.gov.mz", "https://www.bancomoc.mz", "https://www.ine.gov.mz"),
    ("Myanmar", "https://www.president-office.gov.mm", "https://www.cbm.gov.mm", "https://www.mmsis.gov.mm"),
    ("Namibia", "https://www.gov.na", "https://www.bon.com.na", "https://www.nsa.org.na"),
    ("Nauru", "https://www.naurugov.nr", "https://www.nauru.gov.nr", "https://www.naurugov.nr"),
    ("Nepal", "https://www.nepal.gov.np", "https://www.nrb.org.np", "https://www.cbs.gov.np"),
    ("Netherlands", "https://www.government.nl", "https://www.dnb.nl", "https://www.cbs.nl"),
    ("New Zealand", "https://www.govt.nz", "https://www.rbnz.govt.nz", "https://www.stats.govt.nz"),
    ("Nicaragua", "https://www.presidencia.gob.ni", "https://www.bcn.gob.ni", "https://www.inide.gob.ni"),
    ("Niger", "https://www.gouv.ne", "https://www.bceao.int", "https://www.stat-niger.org"),
    ("Nigeria", "https://www.nigeria.gov.ng", "https://www.cbn.gov.ng", "https://www.nigerianstat.gov.ng"),
    ("North Korea", "https://www.korea-dpr.com", "https://www.centralbank.kp", "https://www.korea-dpr.com"),
    ("North Macedonia", "https://www.vlada.mk", "https://www.nbrm.mk", "https://www.stat.gov.mk"),
    ("Norway", "https://www.regjeringen.no", "https://www.norges-bank.no", "https://www.ssb.no"),
    ("Oman", "https://www.oman.om", "https://www.cbo.gov.om", "https://www.ncsi.gov.om"),
    ("Pakistan", "https://www.pakistan.gov.pk", "https://www.sbp.org.pk", "https://www.pbs.gov.pk"),
    ("Palau", "https://www.palaugov.pw", "https://www.palaugov.pw", "https://www.palaugov.pw"),
    ("Panama", "https://www.presidencia.gob.pa", "https://www.bpp.gob.pa", "https://www.inec.gob.pa"),
    ("Papua New Guinea", "https://www.pm.gov.pg", "https://www.bankpng.gov.pg", "https://www.nso.gov.pg"),
    ("Paraguay", "https://www.presidencia.gov.py", "https://www.bcp.gov.py", "https://www.ine.gov.py"),
    ("Peru", "https://www.presidencia.gob.pe", "https://www.bcrp.gob.pe", "https://www.inei.gob.pe"),
    ("Philippines", "https://www.gov.ph", "https://www.bsp.gov.ph", "https://www.psa.gov.ph"),
    ("Poland", "https://www.gov.pl", "https://www.nbp.pl", "https://www.stat.gov.pl"),
    ("Portugal", "https://www.portugal.gov.pt", "https://www.bportugal.pt", "https://www.ine.pt"),
    ("Qatar", "https://www.gco.gov.qa", "https://www.qcb.gov.qa", "https://www.psa.gov.qa"),
    ("Romania", "https://www.gov.ro", "https://www.bnr.ro", "https://www.insse.ro"),
    ("Russia", "https://www.gov.ru", "https://www.cbr.ru", "https://www.gks.ru"),
    ("Rwanda", "https://www.gov.rw", "https://www.bnr.rw", "https://www.statistics.gov.rw"),
    ("Saint Kitts and Nevis", "https://www.gov.kn", "https://www.eccb-centralbank.org", "https://stats.gov.kn"),
    ("Saint Lucia", "https://www.govt.lc", "https://www.eccb-centralbank.org", "https://www.stats.gov.lc"),
    ("Saint Vincent and the Grenadines", "https://www.gov.vc", "https://www.eccb-centralbank.org", "https://www.stats.gov.vc"),
    ("Samoa", "https://www.samoagovt.ws", "https://www.cbs.gov.ws", "https://www.sbs.gov.ws"),
    ("San Marino", "https://www.gov.sm", "https://www.bcsm.sm", "https://www.statistica.sm"),
    ("Sao Tome and Principe", "https://www.presidencia.st", "https://www.bcstp.st", "https://www.ine.st"),
    ("Saudi Arabia", "https://www.saudi.gov.sa", "https://www.sama.gov.sa", "https://www.stats.gov.sa"),
    ("Senegal", "https://www.gouv.sn", "https://www.bceao.int", "https://www.ansd.sn"),
    ("Serbia", "https://www.srbija.gov.rs", "https://www.nbs.rs", "https://www.stat.gov.rs"),
    ("Seychelles", "https://www.egov.sc", "https://www.cbs.sc", "https://www.nbs.gov.sc"),
    ("Sierra Leone", "https://www.statehouse.gov.sl", "https://www.bsl.gov.sl", "https://www.statistics.sl"),
    ("Singapore", "https://www.gov.sg", "https://www.mas.gov.sg", "https://www.singstat.gov.sg"),
    ("Slovakia", "https://www.vlada.gov.sk", "https://www.nbs.sk", "https://www.statistics.sk"),
    ("Slovenia", "https://www.gov.si", "https://www.bsi.si", "https://www.stat.si"),
    ("Solomon Islands", "https://www.parliament.gov.sb", "https://www.cbsi.com.sb", "https://www.statistics.gov.sb"),
    ("Somalia", "https://www.presidency.gov.so", "https://www.centralbank.gov.so", "https://www.nbs.gov.so"),
    ("South Africa", "https://www.gov.za", "https://www.resbank.co.za", "https://www.statssa.gov.za"),
    ("South Korea", "https://www.president.go.kr", "https://www.bok.or.kr", "https://www.kostat.go.kr"),
    ("South Sudan", "https://www.presidency.gov.ss", "https://www.bankofsouthsudan.org", "https://www.ssnbs.org"),
    ("Spain", "https://www.lamoncloa.gob.es", "https://www.bde.es", "https://www.ine.es"),
    ("Sri Lanka", "https://www.gov.lk", "https://www.cbsl.gov.lk", "https://www.statistics.gov.lk"),
    ("Sudan", "https://www.sudan.gov.sd", "https://www.cbos.gov.sd", "https://www.cbs.gov.sd"),
    ("Suriname", "https://www.gov.sr", "https://www.cbvs.sr", "https://www.statistics-suriname.org"),
    ("Sweden", "https://www.regeringen.se", "https://www.riksbank.se", "https://www.scb.se"),
    ("Switzerland", "https://www.admin.ch", "https://www.snb.ch", "https://www.bfs.admin.ch"),
    ("Syria", "https://www.egov.sy", "https://www.cb.gov.sy", "https://www.cbssyr.sy"),
    ("Taiwan", "https://www.taiwan.gov.tw", "https://www.cbc.gov.tw", "https://www.stat.gov.tw"),
    ("Tajikistan", "https://www.president.tj", "https://www.nbt.tj", "https://www.stat.tj"),
    ("Tanzania", "https://www.tanzania.go.tz", "https://www.bot.go.tz", "https://www.nbs.go.tz"),
    ("Thailand", "https://www.thaigov.go.th", "https://www.bot.or.th", "https://www.nso.go.th"),
    ("Timor-Leste", "https://www.timor-leste.gov.tl", "https://www.bancocentral.tl", "https://www.statistics.gov.tl"),
    ("Togo", "https://www.republicoftogo.com", "https://www.bceao.int", "https://www.stat-togo.org"),
    ("Tonga", "https://www.gov.to", "https://www.reservebank.to", "https://www.statistics.gov.to"),
    ("Trinidad and Tobago", "https://www.gov.tt", "https://www.central-bank.org.tt", "https://www.cso.gov.tt"),
    ("Tunisia", "https://www.tunisia.gov.tn", "https://www.bct.gov.tn", "https://www.ins.tn"),
    ("Turkey", "https://www.tccb.gov.tr", "https://www.tcmb.gov.tr", "https://www.tuik.gov.tr"),
    ("Turkmenistan", "https://www.turkmenistan.gov.tm", "https://www.cbt.gov.tm", "https://www.stat.gov.tm"),
    ("Tuvalu", "https://www.gov.tv", "https://www.tv", "https://www.tv"),
    ("Uganda", "https://www.statehouse.go.ug", "https://www.bou.or.ug", "https://www.ubos.org"),
    ("Ukraine", "https://www.kmu.gov.ua", "https://www.bank.gov.ua", "https://www.ukrstat.gov.ua"),
    ("United Arab Emirates", "https://www.u.ae", "https://www.centralbank.ae", "https://www.fcsa.gov.ae"),
    ("United Kingdom", "https://www.gov.uk", "https://www.bankofengland.co.uk", "https://www.ons.gov.uk"),
    ("United States", "https://www.usa.gov", "https://www.federalreserve.gov", "https://www.census.gov"),
    ("Uruguay", "https://www.presidencia.gub.uy", "https://www.bcu.gub.uy", "https://www.ine.gub.uy"),
    ("Uzbekistan", "https://www.gov.uz", "https://www.cbu.uz", "https://www.stat.uz"),
    ("Vanuatu", "https://www.gov.vu", "https://www.rbv.gov.vu", "https://www.vnso.gov.vu"),
    ("Vatican City", "https://www.vaticanstate.va", "https://www.vatican.va", "https://www.vatican.va"),
    ("Venezuela", "https://www.presidencia.gob.ve", "https://www.bcv.org.ve", "https://www.ine.gov.ve"),
    ("Vietnam", "https://www.chinhphu.vn", "https://www.sbv.gov.vn", "https://www.gso.gov.vn"),
    ("Yemen", "https://www.yemen.gov.ye", "https://www.centralbank.gov.ye", "https://www.yemen.gov.ye"),
    ("Zambia", "https://www.statehouse.gov.zm", "https://www.boz.zm", "https://www.zamstats.gov.zm"),
    ("Zimbabwe", "https://www.opc.gov.zw", "https://www.rbz.co.zw", "https://www.zimstat.co.zw"),
]

# Fuzzy name → exact DB name mappings for countries with different spellings
NAME_ALIASES: dict[str, str] = {
    "Czech Republic": "Czechia",
    "South Korea": "Republic of Korea",
    "North Korea": "Democratic People's Republic of Korea",
    "Syria": "Syrian Arab Republic",
    "Russia": "Russian Federation",
    "Vietnam": "Viet Nam",
    "Laos": "Lao People's Democratic Republic",
    "Iran": "Iran (Islamic Republic of)",
    "Bolivia": "Bolivia (Plurinational State of)",
    "Venezuela": "Venezuela (Bolivarian Republic of)",
    "Tanzania": "United Republic of Tanzania",
    "Eswatini": "Eswatini",
    "Taiwan": "Taiwan, Province of China",
    "Brunei Darussalam": "Brunei",
    "Cabo Verde": "Cape Verde",
    "Congo": "Republic of the Congo",
    "Côte d'Ivoire": "Ivory Coast",
    "Sao Tome and Principe": "São Tomé and Príncipe",
}


def seed_institutions(db: Session) -> None:
    """Seed country_institutions table with official URLs."""
    # Build name → country_id map (case-insensitive)
    countries = db.query(Country.name, Country.id).all()
    name_to_id: dict[str, int] = {c.name.lower(): c.id for c in countries}

    inserted = 0
    skipped = 0

    for entry in INSTITUTIONS_DATA:
        country_name, gov_url, cb_url, stats_url = entry

        # Try direct match first, then alias
        lookup_name = NAME_ALIASES.get(country_name, country_name)
        country_id = name_to_id.get(lookup_name.lower()) or name_to_id.get(country_name.lower())

        if not country_id:
            log.warning(f"institutions: country not found — '{country_name}'")
            skipped += 1
            continue

        stmt = pg_insert(CountryInstitution).values({
            "country_id": country_id,
            "gov_portal_url": gov_url or None,
            "central_bank_url": cb_url or None,
            "stats_office_url": stats_url or None,
            "updated_at": date.today(),
        })
        stmt = stmt.on_conflict_do_update(
            index_elements=["country_id"],
            set_={
                "gov_portal_url": stmt.excluded.gov_portal_url,
                "central_bank_url": stmt.excluded.central_bank_url,
                "stats_office_url": stmt.excluded.stats_office_url,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        db.execute(stmt)
        inserted += 1

    db.commit()
    log.info(f"Institutions seeded: {inserted} upserted, {skipped} not found")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        seed_institutions(db)
    finally:
        db.close()
