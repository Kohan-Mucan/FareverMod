# -*- coding: utf-8 -*-
"""Compiled game data for raw_craft, embedded in this module.

The payload is zlib+base85-compressed JSON embedded as a literal.
Decompressed once at import time — `from . import raw_X; raw_X.DATA` keeps
working everywhere (dev + frozen).
"""
import base64
import json
import zlib

_PAYLOAD = (
    b"c-rM%-E!Ny5q=eouG7S#ES((R*^V8jjZZX|Pdsxv84V;s5^9oALDG(LCNq7FzFwcC3;qcb@k`RS+"
    b"+HOX$;J0AcCotv2>#ifOadIE$)tPoXLm+}HSsa)o|ON6yWVu)bms_edB7|pG=z)ZkvIHH@8~bR<6"
    b"EzPa`fwo*L!=^@AdoMAKjmCy8oclsC)AFKfBAtcP@4Tg5as&KfN3IXogqRpJVp!(~O4E<OWAHVKW"
    b"@PU586(X@$vh6?ad(H{FQ*fX9yCzv(`bdAv%019|=7o9+hwc@Hg-Imo>xAxWQQct+Ovn$EG$+yC~"
    b"a8{_YB#39UaG=p0|qIiW_hcajn9tcr@`PH?bFyv>VfFxXbDE{dFgl1w&{oBo&llX`c8<E*P`i|kY"
    b"WW8hvWb@X3zIiUfSC~zaPoltu^V&yYEN5NFiwoxE4>I;+VDG;i`AZV59J_k~k0?5vOT#R{Va`1N8"
    b"-<71@270G!qlhBjSG9kVzNLpMc<b)h3*%BYpMszVunZ@z55j7AbNKTlFmRk_fbINRrcfLGo|r_Ux"
    b"_AHC<ri{9QEF=8D5}iuB=Q$-e8z2<|x(6QK6QtysBFM><0Y5a97qoZ|dDmdQbk(WczsDCYOR3iJ^"
    b"_|ISm3B@;J9<f_@KYZHc-;47VWWVohc(i200{IGiK4>Hd`1;P0W2QMBrSC3Y4*7+=((i_U1n;3wL"
    b"d!jl~yetiDd2K=M*NPNG8(x3gf!_XritUDxx>x@p5DDEKNr<>?)=aRA|?l9~VH1+v^NVuTjVBpMg"
    b"l!{nk^soW@4=4iwDDKQq2o1!mDCU<rrhtOP1;K37nW8xM6~n|<1BH(WM)$L@x(^xWTa3VeBF?9?q"
    b"K}-~jG;x`IXNMq;**oNrJeqkHq?dDB0MQCcXvH**JbKD-Kh_l0&wW6&t1dq$kFFYakX5oe7d2>>E"
    b"yUMoKBLxzv-mdyPHmm-rKGa3vm>smc1hLISxB(`p6TWMIQfCzrf$uKKCkqTZCr}$EjEHKf$SRKzZ"
    b"B%5Bm&beaOuhnqd$@(mUoDuQ52yn#SO01Y8#$4N=TJ1^jf$@SKz$IHlaDIwa0K_yKNDn_4H(Jlu+"
    b"6j#nO-3N4gTsWiFf4wq?K>vE!n*Ydb8NxUF&%oBipj~mZO6j2tr`CKWmmd|BR^Mt;U%W1^8d7MU&"
    b"y~AmQ*!!DCh~C{Ud^DvD#hE9qF<W485>UdFfI~p3#7#Yb>nyc<Fv}Pb@Vw3vv2B!E0HR0mGzdcwi"
    b"qcS(`v!M2@I<NzN~Jv%9<nu%7D5u@g7i^IG{{;m@>l$beP8AwBcJdg$lf^$QMG)dc(|c&XvDbrhD"
    b"MORZ)k+r`-Vn{-ZyUW1LkQRj~L_uDrv~&<^+W^ED1IL`PaX*OpF8pnk7DWsTtcqn&v|o8c`@k(-b"
    b"mDeJBlX%N6&IIR-~bB?3HXgnLyM;=&n<Qoke&Vh>ycE6#&q8j9#T@%haRLRRL7bM)hf4}Wz+3<WN"
    b"lDZDP#$kylbKc6EB6imF9x1CdZU-h)Vg=B#p9F0q<<z)Q9h7P6>;pSWlA@+`?5Mb|A3IV2IgCB}e"
    b"1BDICayG=PrTGI`GGtUNN~@c+?!lqIfqZKgC#etRa{*9WL!~og^l=VG&u9X6pO#%ddf+~`fMP9<-"
    b"gFiT&U|-D=NsNm7KXBTMId)e*12!Nq=ql`6Hc;llGJ9NC2PyAvzC8cgtHao$g*&B2gKcywNh9uUn"
    b"!q%=rB4tZeF94WbZmUDfa%OlVWfpp^ypClFT4PK>>pEu$0D!MdEjsJRjr64xuB7wgn6d!5gOkfHd"
    b"!I=RD2xGKYkU3d1y8luC*CEJW&!Tmqkdi%^)Re{35RiwL$;Msbhm;D07$%>$X#txE2NZ*2{&xr0G"
    b"S4j}q!Jxnz09XI<{2+M4I2JyUm^2-4HAzUYM{#z2l|6rn%i%)HN4T}2|E@_;0eSSl4P~LG#!pR@K"
    b"or~LR3@y2$zAWxgs(^3hr8@+b+vMgNg?#dNa!I(u!n(x%bRi6?+}1#5<Wp`cM_Efs?7brscyD{hB"
    b"?^}o=r6!VRwDXyZW@!DztJhoAan4iQRI%lcXT8p;F$>Y%NxdY5nm=u!S0S!*m)9mzwx;NEYdpz0+"
    b"X9Fj5)PC@?&z&%~DIyb09cy=^+>MlHD|dk-`_rU4hd_JC+BXSDT@y_n$LH!yj1dKUEXlUd#;anoq"
    b"!*da+`oml*Gu=(&$ASoWWWrNk7s7eD$miZ<sf5|hx~So4u&Yppf-4GfN`Ah@M)gMuaKxvKwjMuLc"
    b"jc?W2r4IH2ub^l%mEg!xFY!;Rwh36gBgV!6DcYJ^%GbFPs%8Z?VzCtwG@nwwWlbck6C5z!MiwgAp"
    b"vFS^mIaS7$@fxxFF$&iHjx~xSnjs+gkT`Kc0n`ZRqh8k<*=+(PF=Qp!6<qnC8J}muCv=krDG8MrR"
    b"jGxEglJI)Pj}RC&t$bi;Eibr6O#-pgVUa_1p=pheT+Y+Lw{VNKZB8Dl-+J=A2$@jw+fdTxkB%ED_"
    b"Dl$4_n&x!Qf8U@moNijd;@WxL@sD0l`hN@;T3Je#Ga`OugSq%U3|UPNPscgg*4fINcFZR`!#Myk>"
    b"ey+C^89*9hGh=0ag(25A+dTxcVl*DwuBW-Vf@3T%Y$BNX%)YW5Zp%0xE8_#vGEZ?mH%5)FmxHfOp"
    b";Av_9;yL?Kp-LgANN{iYD3ZH6qCoUQ}SKnI_pMidOMtz66$Ex(s%eTC)sTMW1@QuZ{vKKsE`Q6h_"
    b"E?5<Ac|nsigg&w&>D3}B?Imsb?bVpwu`)7;`dTm}wXb-_`f{M1N3kkC^Gb>rpSI5AP+^NxLGZ|Gu"
    b"PgeNhS;pW&V~%m5a?N%qDzf!(UZqIn#a02H=D;Q%3NDda;U=vPmy)dP>0;5Lbug?y&Aoq<^==$ie"
    b"cSm&gXcXEBNsW)~8?-Zd8=<)yX&s&tWZ|vM$n7911!j{@5oo+-Qy>C6@Q513yhRBOSo|s;>RE_Z("
    b"Up;%4nyPKwLI*(GC|=+6*PJ;TuB2w6~NhQ_tN+@)frPTL8IzSeY&$hLjZDk^>cV-cBUMk4qNnd2#"
    b"6_`c(-<T~ibtyJuL?MdtQi(twq+{ZQsJT11K*4oYuYb$p_S{v#~+61^Stp$MFV!JhzQjsk{&1&w}"
    b"U{=Jn0I?{#TLUQ(*aFPF@NNxdRi0@9+BjvYsRE^?@-><>!ZXBCwh;Jjw}mf@5#JV3@)S2lyDy*DL"
    b"SIx3Quv?wW~Vu9TTsD2Ps02K!51S?T|jnF{~d|uG<Zq)RqHvjSN{#4AICI__*Q>s7V;?um&K}lh2"
    b"Cl&NPm;W3~gpBMl0C#9nm%9DdU}G0*MY>W+{Yfj=(hF{5Fa1<>_$Q&_%Y_Nx4*BmWonEGI-?__O;"
    b"Int|G}#=|-sxgNC0&?Ji88tO@Myy5gH2d4B#<6h{e5Lvsp5NAlQVf<kSk&&#d2n8C0orwO9^^)`7"
    b";aShwy3UAa86}4-fGk9`d4_7__JP|P6oVylQHsZ93%2S3XS)|yH0kV5e!x?`s>~^&YaOE~5(Mxz^"
    b"e|72eL<F*txt?y5rTJ<@QkZ|hK291Zk&X#$H4T?|yymA3>@Lt(-Pwwb`<#PnYSz-QPD#sp7G@l%q"
    b"XlG$E{Wd%nst2<!qZlsFJs_pcHM!f-5XXN>YLb?reYF$jqnaTM=;yUsKVAReDa;JFAMMt94`5Ulc"
    b"&G&18m>Md}Fuq&QGu-+4spZ^C!d2m$30)-MBQ`3Rx|;tMZ<butvcHYYY5JR8FBDg?kpGuyycL4Ow"
    b"s$3T2S@@b{xel)u_&7jA4vEVT;y7Aol5t@<k26?T!bER6Fo2}(A)x)Lm%>iHSkSg1A&vLYys1&7J"
    b";VuKrUOoy=NBG*<jXj>ZSH9#{BobqEm45hSM1FGpbNfR%mEYGlT<XP_|HW}3E6ec>6!C4w;Q*7Z0"
    b"0-)!zhf^Ei#w&uM0b_itrHg6{PcXy`n+>C%X}CP&Cl9QiNC}k&YTJWloo1JcD;4r7gx6xpl=u)X%"
    b"_=#rqY_CIPotE+-Oe%Na3N;zb(Qfn3_XV}Nk*DGwa20I{0*-oG9SZhthgr4{le)`nX2c29mtl2-("
    b"j(IniJ56u&)@#n5P@8WNkdPP82rYuwuA`gAT@zBzPi4?TLRryQxe|Ik-of?;6}=&?pZq8hAl{SlE"
    b"V`r9Fi@_T>wE4D}0rE$SuTM_40C&cnaiapb!w51(Nf`Tut*rh)K(m!6o^IJ0b@+racPvdx%;W_<P"
    b"8l245>X;1!BYeK%K+d>gv`FSn=6KP>bxM3^J{shbz$FYWvd}=~?Z!DPZy-Nkc(pjIIY+E;M)-U-A"
    b"M}awS0csid8SGi}b+|8u#o7bHZPfSa`c<m?+8MTdi`B6ix6AwLm2*;l%TL)WkvqfoYO1^MVkOJ;)"
    b"yk^6y{%WCjx^BwF9!W4nQnB*!7s1fkq>IxisdGy+$&|5a?6)p%BV`^Ew``6R%VpJ{9uL%%dOHgTB"
    b"Xa2Ty1o%_;xPL|H7M(u#RMZUQFKoeXDRXeAV3aA?I~-(}tzjP3_u=S}Om@=7_d>hwO|Pjn;6|pSX"
    b"2g8k+JnQ}&cQ;^v3%xZ+kkSOdD|G#(Xb657GtZc?f|qOaYgw(w11`!?!w-|ALpAMAM&@9q_^Lh>4"
    b"Hb*qHgezoOYG}#k2XxyjGE0NuZCVS#(&<J^f1ETFyHb(4@s*=c<du)lcXqqf^>?d4CFzEvguvqOu"
    b"EX{Q1B^215x3n|hRvP5rc?#ixRJSITuPyFNYo-j?h5;wj&fCFOk=76!TN2lvQbXGn=7OwJVc+6lo"
    b"%6I9cTCVK(i&kqjpOuGs#c)w3u}bzBY|@lS^~Bw%gN663;6ATU>+Z94G8-UiY{#5q|Jb^v^bc`pb"
    b"Wu<n`5g;YlyA%;WnV{3UfiWKanDMusN(b3<p9`tp{xDzs+&&$!Y?t^xo#Ec12mg&aEg;dp75*e4s"
    b")8HJ|f@MQP()j8&nkeCb;*^I7<uu>>{^!s=#wbmStRh0Rx3v1*S<McT7)fbDo-3sKM>52-}Mi8}f"
    b">L-a3J$ZOcEgnuSrj1pmIasGXd7EUSF<An*O={4*#b;VqM|FvD%ZZCPL_xBp{kMAjbruhR)UsGn&"
    b"NWsA3_~ocLrC^`S&|b-V+T59Uq4$%%TEEU%#`j5huLUET<35sMV<c^D`|qi{av$`2b?3Tw<qG3Sv"
    b"v1yn<+w#GXB4s8J=rq@QH`4U^VT@;sK2O<(`$&+v&YHLX4=&6+Fu$X{ly;XH5{l2$*^B*G#NC+IS"
    b"_F6kM!O`H}Ezx?|b)-|5X7~y4-5OF@A)@GjFK!gnLuh_Kq5Z5!Z-dhc17)W3GDZpoX@3Dt|t%fe?"
    b"<EM~Z_CM@g{0SH2@})T7s8r{2&Ff^Yr#{-!RPzFBAbF|hC83VGo0YV_@KQ=G^4I7j3j*BVxOgQh5"
    b"51{TPuE|$xBK!;6%4oyJC*ZqAk!dr$ms;_UPL!J5>3_Y5QJ>5mc+aEioCOyweslQA9*+Yf)2G%az"
    b"v#$n?KAfHBsv4e$HHH=A)>ECUW^j6DI9dZMq*xEwrcI&-kI35dT0!mEJF)aEU+2E>w*tFwuWW^Z^"
    b"lf>W?dP}^O2^Mf$;!S4t*{!j=M|O)Hf#m=&@`_E3l?Oa;K+3*CjZW4wuf9iB1!xJW&QK5w);Xx{0"
    b"p5kzf$}jDc?O5CsX<1hF{_2&M$1LLuh{n%m}S3@A~&E(}>aDsWgSQiicZOR!`k2^1Wa?Al>`?oWg"
    b"q>A-n((V*{5#11>T}dsa*($FT@AaPW0y-xuB=HuS|aqAiXcse;`-PUOXb7H@P`flAMId3n4@X$F<"
    b"!gkBu%cH+E>_AAL2avacFCB*x~lk^J-cJOz%q6#^D_U&T+IT6YEFo(j!>KjB-DkB_PvQe%Isl*;Q"
    b"eb}iU^DlL`OurQSvh=Ip(AvWZo7o?%E!mcQF0@_h##GON^)>%Gd;2zDifx1W&@nHPjl4O)^s{5x="
    b"?WG@u-ER;<;p{n^;BqBr9Yl^2g(G$1odhPRRL(srRuQGguVphYA#j*XPcDOA-*H~MffALvD+khb;"
    b"y@;t+!ukh`)CvuBeL#dq?<6hw#ctA`*r4YwWLldU~E?hEgO^_GB$Wl_>NT>!!%CTGfpx^uTqaOLD"
    b"RVtX0iyMZRLa6bV|Znh}Mzp&MatP^X;t_G76jH7v41gIbQ;9aG!qxqC35oU8QYJv~{Qh$=Zu{4li"
    b"B)4n4sFsK|~*IX%kN1-2@x$K<%CRd8;0K?|Gk)J7lXe!FS<9xmU@g<Rn?8MII>ZzXMulXc&J>Bdr"
    b"1jvtt*ja+nE}9e{cBp6xzVf!F;iZpYTmCZp!(lP!H4vA4cUh#KuE$&<_5hy+7GH#ZedGrggK5S&`"
    b"-IE?1=SDufyVe1Qx!jZFYc{T@cm2{V943$Ds-%e&${rkvm2qh_Hs@cOV%--+sr0dEYhpxJ{i}Zbd"
    b"Q3Ds?{uE9j?2xgoi;k%O~L6inhsa1s{+V8>d0*FwLhyzy16#v71tb"
)


def _payload_size_kb() -> float:
    """Size of the embedded compressed payload (KB)."""
    return len(_PAYLOAD) / 1024.0


try:
    DATA = json.loads(zlib.decompress(base64.b85decode(_PAYLOAD)))
except (ValueError, zlib.error) as _e:
    raise ImportError("raw_craft: corrupted embedded payload (re-run compiler.py)") from _e
