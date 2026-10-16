"""LIC DSF realism tools.

- Realism 1 - Forecast Error: drivers of past debt dynamics (contributions of growth, interest, exchange rate,
  primary deficit, residual) and the forecast errors of the previous DSA vintages against outturns, ranked in
  the distribution of LIC forecast errors.
- Realism 2 - Fiscal multiplier: the growth path implied by the projected fiscal adjustment under a range of
  fiscal multipliers, against the baseline growth path.
- Realism 3 - Invest-Growth: public and private investment and their contribution to real GDP growth, past and
  projected, against the previous DSA vintages.
- Realism 4 - Fiscal adjustment: the projected 3-year adjustment in the primary balance against the distribution
  of past adjustments in LICs.

Ported as the workbook's formulas per block of cells (see inputs.py) and run by the evaluator in inputs.py.
"""
from .inputs import evaluate

QUIRKS = [
    "None found that change values for the sample country: every formula cell matches the template.",
]

SHEETS = ['Realism 1 - Forecast Error', 'Realism 2 - Fiscal multiplier', 'Realism 3 - Invest-Growth', 'Realism 4 - Fiscal adjustment']

# ====================================================================== the sheets
BLOCKS = {
    'Realism 1 - Forecast Error': [
        # row 2: Country
        ('D2:D3', "='Input 1 - Basics'!C7"),
        # row 5: Current vintage
        ('D5', "='Input 1 - Basics'!C17"),
        # row 6: The latest vintage
        ('C6', '=D3&1'),
        ('D6:D7', '=LEFT(E6, 4)'),
        ('E6:E7', "='Imported data'!E6"),
        # row 7: 5 years ago
        ('C7', '=D3&5'),
        # row 11
        ('H11:N11 H99:N99', '=I11-1'),
        ('O11', '=FirstYear_of_Projection'),
        ('P11:Y11 P99:Y99', '=O11+1'),
        # row 13
        ('AE13', '=++OFFSET(translation!C1213, 0,LANG)'),
        ('AF13', '=++OFFSET(translation!C1214, 0,LANG)'),
        # row 14: Current vintage
        ('AD14', '=++OFFSET(translation!C1212, 0,LANG)'),
        # row 15: NGDPD
        ('B15:B17 B19:B22 B24:B27 B103 B105:B111', '=$D$5'),
        ('D15:D17 D19:D22 D24:D27 D103 D105:D111', '=CONCATENATE(B15,C15)'),
        ('H15:T15', "=IF('Input 1 - Basics'!$C$19=lookup!$J$12,'Baseline - external'!G48/1000,'Baseline - external'!G48)"),
        # row 16: D_GDP
        ('H16:Y17', "='Baseline - external'!G12"),
        ('AE16', '=CONCATENATE(I11," -",N11)'),
        ('AF16', '=CONCATENATE(N11, " - ",S11)'),
        # row 18: External debt (in billions of US dollars)
        ('H18:T18 H35:T35 H55:T55', '=H15*H16/100'),
        ('AD18:AD25', '=++OFFSET(translation!C1215, 0,LANG)'),
        ('AE18:AE19', '=N16-I16'),
        ('AF18:AF19', '=S16-N16'),
        # row 19: BGS_GDP
        ('H19:T19', "='Baseline - external'!G18"),
        # row 20: NCTN_GDP
        ('H20:T20', "='Baseline - external'!G21"),
        ('AE20:AE24', '=SUM(J23:N23)'),
        ('AF20:AF24', '=SUM(O23:S23)'),
        # row 21: NCTN_OTH_GDP
        ('H21:T22 H28:T28', "='Baseline - external'!G23"),
        # row 23: Current account + FDI
        ('H23:T23 H40:T40', '=H19+H20+H21+H22'),
        # row 24: DCIR_GDP
        ('H24:T26', "='Baseline - external'!G27"),
        # row 25: DCGDPR_GDP
        ('AE25', '=SUM(J28:N28)-SUM(J30:N30)'),
        ('AF25', '=SUM(O28:S28)-SUM(O30:S30)'),
        # row 26: DCPECH_GDP
        ('AE26', '=-SUM(J30:N30)'),
        ('AF26', '=-SUM(O30:S30)'),
        # row 27: D_LCH_GDP
        ('H27:T27', "='Baseline - external'!G15"),
        # row 29: External debt o/w private debt (in percent of GDP)
        ('H29:T29 H46:T46', '=H16-H17'),
        # row 30: change in private sector debt (ppt change)
        ('I30:T30 I47:T47', '=I29-H29'),
        # row 32
        ('B32:B34 B36:B39 B41:B44 B52:B54 B56:B59 B61:B64 B115 B117:B123 B130 B132:B138', '=$D$7'),
        ('C32:C34 E32:E46 C36:C39 C41:C44 C69 E69', '=C15'),
        ('D32:D34 D36:D39 D41:D44 D115 D117:D123', '=$D$3&"."&C32&"."&$E$7'),
        ('H32:Y32 H33:T33 H34:Y34 H36:T39 H41:T44', "='Imported data'!J14"),
        # row 45
        ('H45:T45 I65:T65', '=H44-H40-H41-H42-H43'),
        # row 48: r: ratio of Old GDP / New GDP
        ('H48:Y48', '=H32/H52'),
        # row 49: g: Nominal GDP growth (USD)
        ('I49:Y49', '=I32/H32-1'),
        ('AE49:AF49 AE52', '=AE13'),
        # row 51: 5 years ago (re-based)
        ('AG51', '=++OFFSET(translation!C1223, 0,LANG)'),
        # row 52
        ('C52:E53 C54:D54 E55 C56:E59 E60 C61:E64 E65:E66', '=C32'),
        ('H52 C71', '=H15'),
        ('I52:Y52 N77:Y77 I130:Y130 N151:Y151', '=H52*(1+I49)'),
        ('AF52 AF133', '=AE52'),
        # row 53
        ('H53:T53 H54:Y54 H60:T60 H66:T66', '=H33*H$48'),
        ('AD53:AE53', '=AD18'),
        ('AF53', '=N53-I53'),
        ('AG53:AG60 AG134:AG141', '=AE53-AF53'),
        # row 54
        ('E54 E71', '=$E$34'),
        ('AD54:AE57 AD59:AE59 AE60 H89:T89', '=AD20'),
        ('AF54:AF57', '=SUM(J60:N60)'),
        # row 58
        ('AD58:AE58', '=AD19'),
        ('AF58', '=N54-I54'),
        # row 59
        ('AF59', '=SUM(J65:N65)-SUM(J67:N67)'),
        # row 60
        ('AF60', '=-SUM(J67:N67)'),
        # row 61
        ('I61:T63', '=I41*H$48'),
        # row 64
        ('I64:T64', '=I33*I48-H33*H48'),
        ('AD64', '=++OFFSET(translation!C2018, 0,LANG)'),
        # row 65
        ('AD65', '=++OFFSET(translation!C2020, 0,LANG)'),
        # row 66
        ('AD66 C77:E77 E78 C79:E79 C151:E151 E152 C153:E153', '=AD58'),
        ('AF66', '=AG58'),
        # row 67
        ('I67:T67', '=I66*I73-H66*H73'),
        # row 69
        ('B69 B71 B77 B79 B143 B145 B151 B153', '=$D$6'),
        ('D69 D71 D143 D145', '=$D$3&"."&C69&"."&$E$6'),
        ('H69:Y69 H71:Y71', "='Imported data'!J30"),
        # row 70: PPG External debt (in billions of US dollars)
        ('H70:T70 H78:T78 H104:Y104 H116:T116 H131:Y131 H144:T144 H152:Y152', '=H69*H71/100'),
        ('AD70:AD75 AD78:AD79 AD149:AD156 AD158:AD159', '=AE70'),
        ('AE70:AE73', '=AD54'),
        ('AF70:AF73', '=AG54'),
        # row 73: r: ratio of Old GDP / New GDP
        ('H73:Y73 H147:Y147', '=H69/H77'),
        # row 74: g: Nominal GDP growth (USD)
        ('I74:Y74 I148:Y148', '=I69/H69-1'),
        ('AE74', '=AD59'),
        ('AF74', '=AG59'),
        # row 75
        ('AE75', '=AD58'),
        ('AF75', '=AG58'),
        # row 77
        ('H77:M77', '=H15'),
        ('AD77 C143 E143:E145 C145', '=AD64'),
        # row 78
        ('AE78 AG78:AG79 AG156 AE158:AE159 AG158:AG159', '=AD65'),
        # row 79
        ('H79:Y79 H153:Y153', '=H71*H73'),
        ('AE79', '=++OFFSET(translation!C2019, 0,LANG)&" 3/"'),
        # row 81
        ('H81:Y81', '=H11'),
        # row 82
        ('G82', '=++OFFSET(translation!C1210, 0,LANG)'),
        ('H82:Y82', '=H17'),
        # row 83
        ('G83', '=++OFFSET(translation!C1239, 0,LANG)'),
        ('H83:Y83 H157:Y157', '=H79'),
        # row 84
        ('G84', '=CONCATENATE("DSA-",D7)'),
        ('H84:Y84 AE130:AF130 AE133 AD134:AE141', '=H54'),
        # row 87
        ('G87:G89 G161:G163', '=G82'),
        ('H87:T87', '=H18'),
        # row 88
        ('H88:T88 H162:Y162', '=H78'),
        # row 99: Public debt
        ('O99', '=D5'),
        # row 100
        ('AE100:AF100 H156:Y156', '=AE49'),
        # row 103: NGDP
        ('H103:Y103', "=IF('Input 1 - Basics'!$C$19=lookup!$J$12,'Baseline - public'!H52/1000,'Baseline - public'!H52)"),
        ('AE103:AF103', '=AE16'),
        # row 104: Public sector debt (in billions of local currency)
        ('AE104', '=N105-I105'),
        ('AF104', '=S105-N105'),
        # row 105: DU_GDP
        ('H105:Y105', "='Baseline - public'!H12"),
        ('AD105:AD111', '=++OFFSET(translation!C1224, 0,LANG)'),
        ('AE105:AE111', '=SUM(J106:N106)'),
        ('AF105:AF111', '=SUM(O106:S106)'),
        # row 106: PB_GDP
        ('H106:Y106', "='Baseline - public'!H23"),
        # row 107: DUCIR_GDP
        ('H107:T109 H111:T111', "='Baseline - public'!H29"),
        # row 110: DU_LCH_GDP
        ('H110:T110', "='Baseline - public'!H21"),
        # row 112: Residual
        ('H112:T112', "='Baseline - public'!H38"),
        # row 115
        ('C115 E115:E123 C117:C123', '=C103'),
        ('H115:Y115 H117:Y117 H118:T123', "='Imported data'!J40"),
        # row 124: Residual
        ('I124:T124 I139:T139', '=I122-I119-I120-I121-I123-I118'),
        # row 126: r: ratio of Old GDP / New GDP
        ('H126:Y126', '=H115/H130'),
        # row 127: g: Nominal GDP growth (LC)
        ('I127:Y127', '=I115/H115-1'),
        # row 130
        ('C130:E130 E131 C132:E138', '=C115'),
        ('H130', '=H103'),
        # row 132
        ('H132:Y132 H133:T133 I138:T138', '=H117*H$126'),
        # row 134
        ('I134:T136', '=I119*H$126'),
        ('AF134', '=N132-I132'),
        # row 135
        ('AF135:AF141', '=SUM(J133:N133)'),
        # row 137
        ('I137:T137', '=I117*I126-H117*H126'),
        # row 143
        ('H143:Y143 H145:Y145', "='Imported data'!J51"),
        # row 144
        ('AD144:AD145 AD157', '=AD64'),
        # row 146
        ('AD146', '=AD139'),
        ('AF146', '=AG139'),
        # row 149
        ('AE149:AE155', '=AD135'),
        ('AF149:AF155', '=AG135'),
        # row 151
        ('H151:M151', '=H103'),
        # row 155
        ('H155:Y155', '=H99'),
        # row 156
        ('G156:G158', '=G82'),
        # row 157
        ('AH157', '=AG157+AG156'),
        # row 158
        ('H158:Y158', '=H132'),
        # row 161
        ('H161:Y161', '=H104'),
        # row 163
        ('H163:Y163', '=H131'),
    ],
    'Realism 2 - Fiscal multiplier': [
        # row 4
        ('F4:K4 C76 C104 C132 C160 C188', '=G4-1'),
        ('L4', "='Input 3 - Macro-Debt data(DMX)'!X7"),
        ('M4:AF4 E76:Q76 E104:Q104 E132:Q132 E160:Q160 E188:Q188', '=L4+1'),
        # row 5: Primary balance
        ('F5:AF5', "=('Macro-Debt_Data'!O45-'Macro-Debt_Data'!O48)/('Macro-Debt_Data'!O56*'Macro-Debt_Data'!O60)*100"),
        # row 6: Fiscal adjustment
        ('L6:AF6', '=L5-K5'),
        # row 7: Real GDP growth rate
        ('F7:AF7', '=IF(ISNUMBER(\'Macro-Debt_Data\'!O107),\'Macro-Debt_Data\'!O107,"...")'),
        # row 16: Persistence (p)
        ('E16:F16 L50:P50', '=D16'),
        ('G16', '=D16'),
        ('H16', '=D16'),
        # row 20
        ('A20:B20 A45:A50 B78 B106 B134 B162 B190', '=A21-1'),
        # row 21: 1st year of proj.
        ('A21 A51 D76 B79 D104 B107 D132 B135 D160 B163 D188 B191', '=$L$4'),
        ('D21:H41', '=-D$15*D$16^$B21'),
        # row 22
        ('A22:B41 A52:A71 B80:B99 B108:B127 B136:B155 B164:B183 B192:B211', '=A21+1'),
        # row 44: Baseline
        ('D44:H44', '="Multiplier = "&D15'),
        ('L44:P44', '="Multiplier = "&D15'),
        # row 45
        ('B45', '=F7'),
        ('J45:J49 J50:K50 J51:J71', '=A45'),
        # row 46
        ('B46', '=G7'),
        # row 47
        ('B47', '=H7'),
        # row 48
        ('B48', '=I7'),
        # row 49
        ('B49', '=J7'),
        # row 50
        ('B50', '=K7'),
        # row 51
        ('B51', '=L7'),
        ('D51:D71', '=S79'),
        ('E51:E71', '=S107'),
        ('F51:F71', '=S135'),
        ('G51:G71', '=S163'),
        ('H51:H71', '=S191'),
        ('K51:K71', '=K50'),
        ('L51:P71', '=$K51+D51'),
        # row 52
        ('B52', '=M7'),
        # row 53
        ('B53', '=N7'),
        # row 54
        ('B54', '=O7'),
        # row 55
        ('B55', '=P7'),
        # row 56
        ('B56', '=Q7'),
        # row 57
        ('B57', '=R7'),
        # row 58
        ('B58', '=S7'),
        # row 59
        ('B59', '=T7'),
        # row 60
        ('B60', '=U7'),
        # row 61
        ('B61', '=V7'),
        # row 62
        ('B62', '=W7'),
        # row 63
        ('B63', '=X7'),
        # row 64
        ('B64', '=Y7'),
        # row 65
        ('B65', '=Z7'),
        # row 66
        ('B66', '=AA7'),
        # row 67
        ('B67', '=AB7'),
        # row 68
        ('B68', '=AC7'),
        # row 69
        ('B69', '=AD7'),
        # row 70
        ('B70', '=AE7'),
        # row 71
        ('B71', '=AF7'),
        # row 74
        ('A74', '=D44'),
        # row 77: adjustment size
        ('D77:Q77', '=L6'),
        # row 78: Impact of adjustment in year
        ('T78:T99 T106:T127 T134:T155 T162:T183 T190:T211', '=B78'),
        # row 79
        ('D79:D99', '=IFERROR(D$77*$D21,"")'),
        ('S79:S99 S107:S127 S135:S155 S163:S183 S191:S211', '=SUM(D79:Q79)'),
        # row 80
        ('E80:E99', '=IFERROR(E$77*$D21,"")'),
        # row 81
        ('F81:F99', '=IFERROR(F$77*$D21,"")'),
        # row 82
        ('G82:G99', '=IFERROR(G$77*$D21,"")'),
        # row 83
        ('H83:H99', '=IFERROR(H$77*$D21,"")'),
        # row 84
        ('I84:I99', '=IFERROR(I$77*$D21,"")'),
        # row 85
        ('J85:J99', '=IFERROR(J$77*$D21,"")'),
        # row 86
        ('K86:K99', '=IFERROR(K$77*$D21,"")'),
        # row 87
        ('L87:L99', '=IFERROR(L$77*$D21,"")'),
        # row 88
        ('M88:M99', '=IFERROR(M$77*$D21,"")'),
        # row 89
        ('N89:N99', '=IFERROR(N$77*$D21,"")'),
        # row 90
        ('O90:O99', '=IFERROR(O$77*$D21,"")'),
        # row 91
        ('P91:P99', '=IFERROR(P$77*$D21,"")'),
        # row 92
        ('Q92:Q99', '=IFERROR(Q$77*$D21,"")'),
        # row 102
        ('A102', '=E44'),
        # row 105: adjustment size
        ('D105:Q105', '=L6'),
        # row 106
        ('A106 A134 A162 A190', '=A78'),
        # row 107
        ('D107:D127', '=IFERROR(D$105*$E21,"")'),
        # row 108
        ('E108:E127', '=IFERROR(E$105*$E21,"")'),
        # row 109
        ('F109:F127', '=IFERROR(F$105*$E21,"")'),
        # row 110
        ('G110:G127', '=IFERROR(G$105*$E21,"")'),
        # row 111
        ('H111:H127', '=IFERROR(H$105*$E21,"")'),
        # row 112
        ('I112:I127', '=IFERROR(I$105*$E21,"")'),
        # row 113
        ('J113:J127', '=IFERROR(J$105*$E21,"")'),
        # row 114
        ('K114:K127', '=IFERROR(K$105*$E21,"")'),
        # row 115
        ('L115:L127', '=IFERROR(L$105*$E21,"")'),
        # row 116
        ('M116:M127', '=IFERROR(M$105*$E21,"")'),
        # row 117
        ('N117:N127', '=IFERROR(N$105*$E21,"")'),
        # row 118
        ('O118:O127', '=IFERROR(O$105*$E21,"")'),
        # row 119
        ('P119:P127', '=IFERROR(P$105*$E21,"")'),
        # row 120
        ('Q120:Q127', '=IFERROR(Q$105*$E21,"")'),
        # row 130
        ('A130', '=F44'),
        # row 133: adjustment size
        ('D133:Q133', '=L6'),
        # row 135
        ('D135:D155', '=IFERROR(D$133*$F21,"")'),
        # row 136
        ('E136:E155', '=IFERROR(E$133*$F21,"")'),
        # row 137
        ('F137:F155', '=IFERROR(F$133*$F21,"")'),
        # row 138
        ('G138:G155', '=IFERROR(G$133*$F21,"")'),
        # row 139
        ('H139:H155', '=IFERROR(H$133*$F21,"")'),
        # row 140
        ('I140:I155', '=IFERROR(I$133*$F21,"")'),
        # row 141
        ('J141:J155', '=IFERROR(J$133*$F21,"")'),
        # row 142
        ('K142:K155', '=IFERROR(K$133*$F21,"")'),
        # row 143
        ('L143:L155', '=IFERROR(L$133*$F21,"")'),
        # row 144
        ('M144:M155', '=IFERROR(M$133*$F21,"")'),
        # row 145
        ('N145:N155', '=IFERROR(N$133*$F21,"")'),
        # row 146
        ('O146:O155', '=IFERROR(O$133*$F21,"")'),
        # row 147
        ('P147:P155', '=IFERROR(P$133*$F21,"")'),
        # row 148
        ('Q148:Q155', '=IFERROR(Q$133*$F21,"")'),
        # row 158
        ('A158', '=G44'),
        # row 161: adjustment size
        ('D161:Q161', '=L6'),
        # row 163
        ('D163:D183', '=IFERROR(D$161*$G21,"")'),
        # row 164
        ('E164:E183', '=IFERROR(E$161*$G21,"")'),
        # row 165
        ('F165:F183', '=IFERROR(F$161*$G21,"")'),
        # row 166
        ('G166:G183', '=IFERROR(G$161*$G21,"")'),
        # row 167
        ('H167:H183', '=IFERROR(H$161*$G21,"")'),
        # row 168
        ('I168:I183', '=IFERROR(I$161*$G21,"")'),
        # row 169
        ('J169:J183', '=IFERROR(J$161*$G21,"")'),
        # row 170
        ('K170:K183', '=IFERROR(K$161*$G21,"")'),
        # row 171
        ('L171:L183', '=IFERROR(L$161*$G21,"")'),
        # row 172
        ('M172:M183', '=IFERROR(M$161*$G21,"")'),
        # row 173
        ('N173:N183', '=IFERROR(N$161*$G21,"")'),
        # row 174
        ('O174:O183', '=IFERROR(O$161*$G21,"")'),
        # row 175
        ('P175:P183', '=IFERROR(P$161*$G21,"")'),
        # row 176
        ('Q176:Q183', '=IFERROR(Q$161*$G21,"")'),
        # row 186
        ('A186', '=H44'),
        # row 189: adjustment size
        ('D189:Q189', '=L6'),
        # row 191
        ('D191:D211', '=IFERROR(D$189*$H21,"")'),
        # row 192
        ('E192:E211', '=IFERROR(E$189*$H21,"")'),
        # row 193
        ('F193:F211', '=IFERROR(F$189*$H21,"")'),
        # row 194
        ('G194:G211', '=IFERROR(G$189*$H21,"")'),
        # row 195
        ('H195:H211', '=IFERROR(H$189*$H21,"")'),
        # row 196
        ('I196:I211', '=IFERROR(I$189*$H21,"")'),
        # row 197
        ('J197:J211', '=IFERROR(J$189*$H21,"")'),
        # row 198
        ('K198:K211', '=IFERROR(K$189*$H21,"")'),
        # row 199
        ('L199:L211', '=IFERROR(L$189*$H21,"")'),
        # row 200
        ('M200:M211', '=IFERROR(M$189*$H21,"")'),
        # row 201
        ('N201:N211', '=IFERROR(N$189*$H21,"")'),
        # row 202
        ('O202:O211', '=IFERROR(O$189*$H21,"")'),
        # row 203
        ('P203:P211', '=IFERROR(P$189*$H21,"")'),
        # row 204
        ('Q204:Q211', '=IFERROR(Q$189*$H21,"")'),
    ],
    'Realism 3 - Invest-Growth': [
        # row 2
        ('B2:B3 D4:E4 B5:D5 B6:E7', "='Realism 1 - Forecast Error'!B2"),
        ('D2:D3', "='Input 1 - Basics'!C7"),
        # row 11: Efficiency of Investment (φF/φH)
        ('C11', '=C12/C13'),
        # row 15: The current DSA
        ('C15', "='Input 1 - Basics'!C17"),
        # row 16: First year of projection for the current DSA
        ('C16', '=FirstYear_of_Projection'),
        # row 19
        ('C19:H19 C49:L49', '=D19-1'),
        ('I19 M49', '=$C$16'),
        ('J19:N19 N49:R49', '=I19+1'),
        # row 20
        ('B20:B21', '=++OFFSET(translation!C1267, 0,LANG)'),
        ('C20:N21', '=IF(ISNUMBER(\'Realism 3 - Invest-Growth\'!G57*100),\'Realism 3 - Invest-Growth\'!G57,"")'),
        # row 23
        ('B23:B24', '=++OFFSET(translation!C1269, 0,LANG)'),
        ('C23:N24', '=IF(ISNUMBER(\'Realism 3 - Invest-Growth\'!G61*100),\'Realism 3 - Invest-Growth\'!G61,"")'),
        # row 26
        ('B26:B27', '=++OFFSET(translation!C1271, 0,LANG)'),
        ('C26:N27', '=IF(ISNUMBER(\'Realism 3 - Invest-Growth\'!G53),\'Realism 3 - Invest-Growth\'!G53,"")'),
        # row 29
        ('B29:B30', '=++OFFSET(translation!C1273, 0,LANG)'),
        ('C29:N30', '=IF(ISNUMBER(\'Realism 3 - Invest-Growth\'!G82*100),\'Realism 3 - Invest-Growth\'!G82*100,"")'),
        # row 32
        ('B32:B33', '=++OFFSET(translation!C1275, 0,LANG)'),
        ('C32:N33', '=IF(ISNUMBER(\'Realism 3 - Invest-Growth\'!G86*100),\'Realism 3 - Invest-Growth\'!G86*100,"")'),
        # row 39
        ('C39', '=++OFFSET(translation!C2029, 0,LANG)'),
        ('E39', '=++OFFSET(translation!C2030, 0,LANG)'),
        ('G39', '=++OFFSET(translation!C2031, 0,LANG)'),
        # row 41: Contribution of government capital (G)
        ('C41', '=AVERAGE(D30:H30)'),
        ('E41', '=AVERAGE(I29:M29)'),
        ('G41', '=AVERAGE(I30:M30)'),
        # row 42: Contribution of other factors
        ('C42', '=AVERAGE(D33:H33)'),
        ('E42', '=AVERAGE(I32:M32)'),
        ('G42', '=AVERAGE(I33:M33)'),
        # row 44: Real GDP growth
        ('C44', '=AVERAGE(D27:H27)'),
        ('E44', '=AVERAGE(I26:M26)'),
        ('G44', '=AVERAGE(I27:M27)'),
        # row 53
        ('A53:A54', '=++OFFSET(translation!C1265, 0,LANG)'),
        ('B53', '=D3&"."&$B$51&"."&E6'),
        ('C53:R53', "='Imported data'!G60"),
        # row 54
        ('C54:R54', "=IF(ISNUMBER('Baseline - external'!D52), 'Baseline - external'!D52, 0)"),
        # row 57
        ('A57:A58 A61:A62', '=A53'),
        ('C57:R57', "=IF(ISNUMBER('Imported data'!G62),'Imported data'!G62,IF(ISNUMBER('Macro-Debt_Data'!K63),'Macro-Debt_Data'!K63,0))"),
        # row 58
        ('C58:R58', "='Macro-Debt_Data'!K61/'Macro-Debt_Data'!K57*100"),
        # row 61
        ('C61:R61', "=IF(ISNUMBER('Imported data'!G63), 'Imported data'!G63, IF(ISNUMBER('Macro-Debt_Data'!K64), 'Macro-Debt_Data'!K64, 0))"),
        # row 62
        ('C62:R62', "='Macro-Debt_Data'!K62/'Macro-Debt_Data'!K57*100"),
        # row 65
        ('A65:A66', '=A53'),
        ('D65:R66', '=IF(ISNUMBER(D53), C65*(1+D53/100), 0)'),
        # row 70
        ('A70', '="Actual Share of GDP (FAD Database, actual through "&\'Imported data\'!$B$61&")"'),
        ('C70:R70', "=INDEX('Imported data'!$G$59:$V$61, MATCH($A$70, 'Imported data'!$D$59:$D$61, 0), MATCH('Realism 3 - Invest-Growth'!C$49, 'Imported data'!$G$59:$V$59, 0))"),
        # row 71: Actual Level (3.*4.)
        ('C71:R71', '=IF(ISNUMBER(C70),+C70*C66, "")'),
        # row 74
        ('A74:A75', '=+A65'),
        ('C74:L74', '=IF(C$49<=\'Imported data\'!$B$61,IF(C$49<$D6,C$71,IF(ISNUMBER(C57),B74*(1-$C$10)+C57/100*C65*$C$13,"")),IF(ISNUMBER(C57),B74*(1-$C$10)+C57/100*C65*$C$13))'),
        ('M74:R74', '=IF(M$49<=\'Imported data\'!$B$61,IF(M$49<$D6,M$71,IF(ISNUMBER(M57),L74*(1-$C$10)+M57/100*M65*$C$12,"")),IF(ISNUMBER(M57),L74*(1-$C$10)+M57/100*M65*$C$12))'),
        # row 75
        ('C75:L75', '=IF(C$49<=\'Imported data\'!$B$61,IF(C$49<$D5,C$71,IF(ISNUMBER(C58),B75*(1-$C$10)+C58/100*C66*$C$13,"")),IF(ISNUMBER(C58),B75*(1-$C$10)+C58/100*C66*$C$13))'),
        ('M75:R75', '=IF(M$49<=\'Imported data\'!$B$61,IF(M$49<$D5,M$71,IF(ISNUMBER(M58),L75*(1-$C$10)+M58/100*M66*$C$12,"")),IF(ISNUMBER(M58),L75*(1-$C$10)+M58/100*M66*$C$12))'),
        # row 78
        ('A78:A79', '=A53'),
        ('C78:C79', '=IF(COUNT(C74:C74)=2,C74/#REF!-1,"..")'),
        ('D78:R79', '=IF(COUNT(C74:D74)=2,D74/C74-1,"..")'),
        # row 82
        ('A82:A83', '=A53'),
        ('C82:R83', '=IF(ISNUMBER(C78)=TRUE,C78*$C$14,"..")'),
        # row 86
        ('A86:A87', '=+A53'),
        ('C86:R87', '=IF(COUNT(C82,C53)=2,C53/100-C82,"..")'),
    ],
    'Realism 4 - Fiscal adjustment': [
        # row 8
        ('F8:H8', '=G8-1'),
        ('I8', "='Input 3 - Macro-Debt data(DMX)'!X7"),
        ('J8:T8', '=I8+1'),
        # row 9: Primary deficit
        ('F9:T9', "='Baseline - public'!L23"),
        # row 10: 3-yr Fiscal adjustment
        ('I10:T10', '=-(I9-F9)'),
        # row 14
        ('C14', '=++OFFSET(translation!C2024, 0,LANG)'),
        ('D14', '=K10'),
        ('E14', '=ROUND(2*D14, 0)/2'),
        ('F14', '=IF(E14<$A$24,$C$23,IF(E14>$A$49,$C$50,VLOOKUP(E14,$A$24:$C$49,3,FALSE)))'),
        ('G14', '=VLOOKUP(F14,$C$23:$D$50,2,FALSE)'),
        # row 23
        ('D23:D50', '=B23/SUM($B$23:$B$50)*100'),
        ('Y23', '=++OFFSET(translation!C2025, 0,LANG)'),
        # row 24
        ('E24', '=D23+D24'),
        # row 25
        ('E25:E50', '=E24+D25'),
        # row 50
        ('A50', '=++OFFSET(translation!C2026, 0,LANG)'),
    ],
}


def compute(book, sheet):
    """Fill every formula cell of `sheet` from the book's current values."""
    evaluate(book, sheet, BLOCKS[sheet])
