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
    b"c-rM%+j84Fvi%j6p0g8+x+LQ_+p*)!#5*d>JFeQNQYuJ-B#cQy1Cn->U8y?1aei;UWE#8)5^*Kz+"
    b"nlGwBH380(T(l~K=7~bbQ<6oO{d-Czq)f8Y>1Cp_qhD;+s(H7rn^9J%ROchp&?xKj=a%ty`$ee@1"
    b"{369=t#9dv6E*_ruZf&+e}`-G9<q)II*6zq+gC4=#2Ig5aq?KEE6LXpYy^Utsp`^PGm!^cqJrVRI"
    b"b4-GnP>X^qKh9e0ntH{FQ*gvSOS-gF<xB3`GzfxQ0cO?M0be1Mk70_0wikfhHtJSQ7`MHkrT?SFs"
    b"Mjq#5-;t&=%n!~N1P`t*hLm9LO4}>Vd{OZO}81gewKoYLp7k_krK{GL>{>^s7NqoYHjmi8D{lIWr"
    b"vRN?%vUzL2-aHlIOU!1-CsE+SdE=unma{J8#Rc>72O0Ybu=k&j`~`{Dj@`Y4M-&~-rC}D}FlV0sj"
    b"l!4M?<Z`&#?+^)tqXg^VzNYYMc<b)h3*%BYpMszVunZ@z55*FAbNKLl1@Q4cTqs%b@t=*3#IXtUx"
    b"}udC<ri{9`)XC7+#`TuB=Q$-f)yE<|x(6QK6QdysBFM>IVG3a97qoZ|dE3dQbk(boY4PCYOR3iJ^"
    b"_|84Us$@;J9<g8m5SZHc-@47VWWd_(3fi1~t7I9wpM?f#P3;2)unQMB%WC3coR7+=((%g%Vq;3wL"
    b"d!IK>xetiDd7W||0KzzT0(x3gf!_WgCtUDxx>x|BlDDEKNr`zal=Yp~o?l9~VH1qj?NVufnVBpMg"
    b"l!{nmbiW1r4=4iwDDKQr2o1#RDCU<rrhtOPCBbalnV~rL6~n|%1BH(WM)#|*x{n#>8;rnzBF?9?r"
    b"VpIjoS|jhIX)(!;^X7DrJeqsHq?dDB0MfHclSMR-(~7L-H8vF0&wW6&t1Xo$kFFYakX5oe7d2>>E"
    b"yUMoKBLxzv-mdyPHmm-rFt_3vm>smc1s61r9qK`oI&OWgh=izra5>KKCkqTZHEf$EjEHKf$SRKzZ"
    b"B%5BmaReaOuhnqd$@(mNIyZ!kE`hQ{D%1Y8#$4N=TJ1^jfy@Pd>cIHTOBIwa0K_#SRgo7yDMJlu+"
    b"6j#nO-3N4gTsWiFf4wq?K>vE!n*YdcpNxUR+%oBh^kDJU%6j2tr`CKWmmd|BR^Mt;U%W1^8d7MU&"
    b"y~AmQ*!!DCh~C}KeKeyC#hE8<Fk5195>Ud7fI~p3#7#Yb>nyc<Fv}Pb@Vw3nv0ao}0-^`-Gzdcwi"
    b"qcS(`v!M2@I<NzN~Jv%9<no#7D5u@g7i^IG{{;m@^}1zeP8AwW1sLL$lf^$QMG)dc(|c&XvDbrhD"
    b"MORZ)k+r`-Vn{-Z!rCJ?3d0j~L`0Drv~&76gTJED1IL{@?%0GBFYaXrB1orRHo4X_^mVXiT9LO;g"
    b"Aq^`SJlt=8N-78o2Ql?d>l5$;u4hzsW^O8t^Bh&^x(tT+#bX(*zb#OF6N2w9mQF3``PKK#`QF%-C"
    b"HuJF24BRikV|9pxhP%!aY-gZXmUDeb65t1c#a5OHZmXq-Z8#<Umgqw3IgxEWlLV&$fDFm2;4Zbfz"
    b"4HPyk%h?dGmKOJ5$&gX8D6MYNx(A2;7V@omoTNUK&jmnj4VBKE(T4>XJ);TOeOh+;=$`x75{k7rd"
    b"ed1ZIP={ZU2J(fSs2RV6@lC>+2p<jlN!F%PdLfKNm846lB_Ma&RYI)9?sX0Bg?|kEf9B0)=FWue5"
    b"HK4p~L9pxOt6ElD+Hbq}cn9PKv>aghD1jD>8==1qBGs!%`X_mWkh4@qCOMJA{rT+7&P;1aFxA6Vk"
    b"l5owGF0%N!CaDh$(XQ7R?kvk<8_atVC;Eka?M{;^$9EF#!m8O1%Kga4I~4G&~ew<@_8zO^&7<_-o"
    b"SIe_S^^)S(}_uTAzAuO};ImGks@%th8L%2!e{I?{8|G`8j7oXbl1{C)>T+uk~`uv98u)O1fgwsEJ"
    b"dlz@t7+P^feO=z7Q~}@1OScFrx9Rm23i;&k^n!4Qg>{L;=|UJ(xvhcB$fw*?j<S}N*n3AN@ZRo@3"
    b"ly#_(4T{itVQ%^+%%@w|DZFNLFV93qR1V8@90QIz%vo(mp4r4GQLQdg552tu=6DBe&=%oSfqCf1g"
    b"6)g7;|d3<mdE^o28bZ=Rk1i(nBuhCA(=1BZV)Ly9B3?_AC!NuQo$Z??0!EhCi{^f2t<9yO<f+6`z"
    b"1L^<u?FFEHLS(K8=gu<Sn$ONlA&E`IW96m8GeBqpJ|vF0Pm&RT2m8yXx@L2yUm8U-uRb5;Lmj06!"
    b"4^A6BL8#+KU>i&ZcT0VRU*eonV3eP*L2d_6O@AwEsW=Q6jlo>n!Y>jBN=gSx^rq`(iOBSPj78U4+"
    b"W7F3>bE=FhlMP~b6BKOxJ!=$4G($k}A#vh@0;mzr#=WjJvYP}-V#rFcE4cDOGd|CRPv|BMQW7dLs"
    b"!|IR3DKeqp6;mOp2=#3z#G#LCMFqH2B!mE3j|L1`WSyshkj6^KZTKFoZW6|AJ-JZw+fdTxkB%^Yg"
    b"mTh4_n&xi@}|)<F|l38}X#$alhKR0)p#e<#UnQ{Fu+5nR>sKmM?*HokpQ@2z}^{NxCDVtn8;1dCl"
    b"~aw2Q7HuMxTl%!R_n4ALq@xzI*9uV5OM%v;1*71#*hCn)GK)a)%Hl!<JF@nbpz-eyNjBpM3WUCwl"
    b"aLU<GwclnfHyJdHlloquQ6h77JPFyr{uD*99z5xC3l==>Jk5%cNmv4DpQ!Q$2;Twx@WiNQT^1G*<"
    b"T(BzK@`5I32z_Kl(yK*M+DqE<+p96VV`XFx^|fF|YG3h;_2p1Ik78AP=9LsLK5d=Jp~4oYg5Z($L"
    b"09xG4Y65$oedeBA<(ljMVA`eq9+GBngd;(o6TbtWv;C!In?2Tr^q^Jq(kmfq1$S{UX5N)^MZkW!?"
    b"13%;B!3A75rok>r=1^H!8~b>SUaR=cpD>Sr_RkjszVMf8vulZZt=c63ctjfuAOukq+Q}Ro8w$cn+"
    b"-$akF+UC&gvq?2<7}^k)dDo?+;5ge<5sL*rUs?o+W+r|pD9Uu(KXWV=3S6_q~!v53qvBN6<CEbxp"
    b"keBbg_avk(RD;4`ed(yi7JeV;G_pz-3Pm8UmwYGD^+R9y!)`ohLHUS<=YXRV{*lrD_RAdWKvzog#"
    b"m=$p?KrD*x)<8-Gwg59Pyjw$Am1kOjHcnY;sz7O}e1#T_@C<RBEd+kwZ{h25%(q39JjIRC?#t)3&"
    b"=*yM6#f^!*=YgW7F6)hk}!Wk@Yx7d7myv)e@mhT4W1Kz)q0NX)ql<B$1zPJzSZBEg?x&^Ww9z>p|"
    b"_d`(%&R8Lz~%(@ftRLM|1;u%4BbuK%xVeSqh<=BQOoPxJjZrc{*G+be`>XQZAL3rJ_`k3|={feeL"
    b"stt4Q*5x=|{_pyB6Gy9?7N8v?t#F8QWMo}WJ##c{&Y(3}F%ksLToP^iuHX}J{_GZ^;dG(l9q-X^a"
    b"pu3$S{;f?yCqIRuw3QsQT;mQYqM*^msbJxPkMx0hrdCKr4ixh`3Kz7ebIOp$$-K@6(uH0rMdI4|j"
    b"uP=O_h(I>7(9><QG+%8<3iD6c$4TQP(lLRprr`=tHvF`K{RR4}J6o}FpL0-6%~~4P329l+!i)oTw"
    b"15oJ1=0Iov#u{fc-qR-Wei-+t~(I5d&8<jeG~iAR7^sz5#C{E2xeOuRoL3OPks>gbqSt<!xf)!^7"
    b"J=;gzejyZ|pYS`5AU3`#xD^{$#lM0yh4u8<$2~A*<zfRo+t))+l&rZGqp2$|=;NaL-~Cwhn%(Aq$"
    b"Q|p$zgK{(jV$@>d(}!j0{SrB*@TLIr)hRbM5$!Y)#lg>k-2f|8A{t^`Y`dU}R77OKsHtO$x@!OP@"
    b"$zQqkWrbF0Mk!vd%v@H$v8lag5PWZ7NhEiIs0o8Pzq={!zmS<Qv@~n3fn+)n?1{0mg;4BTaDYozk"
    b"0nl^V!>J8$lQqH6fHA(+(nYm}M;Ky8&4$r0G+dqXlLyw1q=ZTXwe7*OPP0qJl?wSB!fUZ)MtlgDW"
    b"|a);s6^7l<0z$Xw{y%mT!`6wU1dBDL(gGLl9A?K?eS81{*E^hSxn$HR$P<jVd3;rnX2c29mtl2-^"
    b"*g@G$)`BVc#%}F^@M`$=Y~qohWR)Va0F(2OUfvNbpFCIuQSKc2k*_a&V6{-!-_$uu&dZH1Lf2u&@"
    b"m=OM47;9Lg8=80r`LTGUIvkFZ9PoQHq2<H&bWzI=vd<p1xbm<GcCUV36u<IJ*sZbQ?{$TnjVn)B6"
    b"XOFlKmqyzbntqJ*_ZVN?x<L9;bkEDe?;fAd=hZ8Up9LE|u@~H{oy|G|+@GcbyOJ{wqvu)k5S-<2f"
    b"90lgQ1*m1*r?6+u*Wtbp7HeM+Zlk_WHm_3MSI)5ITdW3V+%E5{SI$ZKJwIiyMD7gRtEuk3i<PX>S"
    b"1YUP_I6%*GS)!vKO6MxWVY2I2fw^>M?S1+E0&v-a<7zK$}L}ZDWfWtx7xiLTbWS?^Me^8EVoL}Xq"
    b"7H6a<$R5;@i0}{|j$E!a9=uc`<qS_pQRo=v8ymhn&~VO&gY8H?=D#YN`Aqn<Lul9kMfKG}^#Pf8y"
    b"40X=uvROxaWJh?^h2<BD7HU=8S+(|A;%NoWUmw@In;h`x4{+QN5*?c1o!eXCoYeXwUqyuVkx3dw7"
    b"*)vXd{`_-2B(PU59pmCozuS9kun(T?kK_lb^4v2P7*%+}qs!Aeb?y(ipqG__wahPx!!K4o~z+$xr"
    b"u{6`Ymr!7L-pbB^TWOGg=P85(Qr((VzP5NMt(h`l8wQ+AyJ!bnMOs5_Y(-pqN)2sam<zH>g?)pAP"
    b"0rI|+%Z9`NNa@cB#zTlsak<{D6A2(PXx|gXbISXEGIiVEZ}zof_Z$bH6R=|D7vtHlQsjw%Hm)ugE"
    b"9mcZjP-Yts%D3hueU*FU$qm;Y5ny!RD~$FdPU$wH~mY|2D^UAgc+i(tDeu+81U0I=7-Y?b)2K@{t"
    b"Dl*L=<r7Nw1IF;<1D@}+ON%qQV<$`aT#2&<dz(UFUM5;osp#i~6b6=_ex0k-3TEkr?kJfsp0C+g_"
    b"m4AH+>A+KRC6aJZi2}*>W#rgL+S~#Uxj~6DCW>>J!)D?62{nvJ3yS?P0-rsA)Ke?mundXlyeNCCo"
    b"A_W7B<Cml2l!8MpBYPzuXmfAgh2Bm3YW+H6ncOAeofeE}j)zD_jghpq?Z2n)%0ti})Sc_zm1~S6&"
    b"AxdPmO+bHPAOuwd$MN+q8c^x=dE$xQh!++r`HgtXOEMg&9trGweK4ueQ%HS3Jz3+WZ17YnhYD_91"
    b"1x5M|y9eTX-9p_q}_^|4ji?y4-5OF?oQ)Gq0)ggnLuh_Kq5Z5!Z-dhc17)W1)KMpoX@3Dt{i-KnO"
    b"?7BgH|6<0RPJDc_Md>d|YlQ?Kb3!MFZ=e_Iz#->ftJ7}$4kg*<S0HTrhY6z9Mm=a}5#TEj|j*c7G"
    b"9zycZ7`D#@U=%^{skqM~yy1x%bc*D?E_4SQ(s8e5qp+|GEr@N?l`(w}4q~}>F^>@KPd#KRf(AtH2"
    b"_SK-#hqLosRm1bB#;{`Cda85P3{KAsM{8h(6zc)ov`N(95m|d)E2uqtCzhV&>)iMKR$%w-m8~$4z"
    b"AZ1a{R~>6G<Z5nR`xY)h1IY<udp<*Q7gDdrg<e;upo;BN3Jt5`FAF>J>=pMN#X}6>z{A6+ZQtCU+"
    b"A3smE!kE`R<`OnaU40{01j?eq}QqLi;md#%NP{*S}wxMvM+lr75&kJlv|Xdg@M*?*-cf>E7pO6yD"
    b"ni;RS#g8@LP`aFHq6vtlYajzyS(gRd+5zVQCAp)Z~gZE@^K73}_TBF_%Ac%!olRC>0{^W#NIGpHO"
    b"V^z2}F6X#X5-$=HQ<AByGAwC?Qq+dv|gTKEORmkD9Zx{2=iAc_ec_}=szCk3VGRC1L8|A8yO6&`#"
    b"4?ERk{-y4g>6c=kmwxpdS_e2`GyA=@CEJqEg|<uGnCdyOzT#hJZ{Oxiv28FPIp#&Okv9jJes(N7U"
    b"BO}q_Szk~TzN>co(c`C^vARAK$+m@pk7U(DgceSR2|lt(C1)W&BZF<Y?HD&#P?)B3x8xbcAF%x4*"
    b"629_4X?b@ehu~6?O6O;0Ryo5MDV+M52&>js2C6PtSAAP>LkVo~%Wv5{15E-4q#CtGW?|zHr^>lAJ"
    b"67YgIElk*`=UMS|9<W<;TF=th_u)G6nK{a9*B4U4SMpq4?qV`}?6_YdZibCsUFrzdL@Q6-0ozYOj"
    b"4wC~6Y3@XRhHCM{PQRpwtT=vd>lPg7afMIjp$j_92X)4OT<9v1a@g<Rn?8MII>ZzXMulXc&J>48E"
    b"1jvtt*js|pE}9e{cBp6xzVf!A;f0T2TmCBh!(lP!H4vA4cUh#KuE$&=b`PHg7GH#ZedLE0gK5S&`"
    b"-IE?3#uRSJ&o}zrYe5+Uff%w;QNIv!H~1hRp?lco^;`5Z#P19?d6OzmTY3Yu$fJ;Sfp3WeKf8;=^"
    b"h0QRjXOTI$ZZ>310@;ET4dLE7~Tz6a0d#*f<SZhiN_y`u*2`0M|}Zng"
)


def _payload_size_kb() -> float:
    """Size of the embedded compressed payload (KB)."""
    return len(_PAYLOAD) / 1024.0


try:
    DATA = json.loads(zlib.decompress(base64.b85decode(_PAYLOAD)))
except (ValueError, zlib.error) as _e:
    raise ImportError("raw_craft: corrupted embedded payload (re-run compiler.py)") from _e
