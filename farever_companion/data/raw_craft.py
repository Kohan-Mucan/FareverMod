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
    b"+HOX$;J0AcCotv2>#ifOadIE$)tPoXLm+}HSsa)o|ON6yWVu)bms_edB7|pG=z)ZkvIHH@8~byue"
    b"V42lfnCw!7p#$A0K=D-XGncZ@T}W)2Ms$_dmPK#dj`t0fOME-#@(@`Dlh$)SqMa?$eBh(c}h4G+{"
    b"Fwy<LY(XlaGXaus(^yf@v5{D8-f-@oZTl6kyJe*<~_;hXLT{&^2AkvYh{CLu|mWq3x`_?phK&)fg"
    b"@rW@n$al|3aaWsQlKcaYrS%)%c4;~0nfce$6pD^TSqJSh^c_{wq{)A>?O8wi-nv?j55gU=&J^GH}"
    b"wq(6z2xRlte!h7w!dIA0kx!z)h4b1+VJv4|$cqc+<qtCUV_@&U9QjKUtsJ|10gos;oJ+$jz+uij{"
    b"~Lve*zc!ow!+k>%Z&?r#A32QGezH*GKKCJe`~4-%3_8{9KHJ#;~;u>3zE)2H}_FM;#KzJ<TIu5gk"
    b"Om!S11TDn;iAtt{GmSX|AkHL*8JRD&{EF%Tb}0t-PvQ{_F<)zi?O9K5y#XO?prM&t&^}-X@oV7>S"
    b"{c?l}zt81gu`W`ceXXKjhPK@7Jb=3-4|Er|JympGgww(0(q*x>J>k5RPhfF*VoJ{Vurp^MIF!{8^"
    b"{nZlDD9)5iO*9QEf^GJNZgVLY<xWmvRAFMkhgzJn>lPK;W-=~}CZRe7*CGIfn6EyYte@M8X;9%g)"
    b"ag>T!Vf3&8`wu7s04VOvPzVjgt0?A|Ii`Su#09}@)0v_;_7%g#Rs)5P2uAm_u(}T!=Ua@xe<IGOv"
    b"!aij+Kiz^+&MWRpyHF0x22u_mNwLd(IPx4FL!r6Zr5e%I^C%cm;!L<s?S}+?a0yRN^!MZu6(+o$L"
    b"Zv_Ih;<Cy}#+C*t?rfir(9<5DRe>rIx)S^EnPXYx>9&o<$!2Q@_C9*FN_uep`fR49BTg@;||;a6o"
    b"z701x{NV|~cY7n)%ZLDD<s7_Tun&6>vGXarmr9t}~<Jq7%9$?%+%9yq1kr#d9gJoo`_Pn%jN&^+9"
    b"VVvbiHm<lbFQK>Y!<_?!>TI+J6h1c@9FG;*0am*8deUBT@NEA^Px%pfvu$IqdPxFMnk;`esxOtpL"
    b"kiElcgxLF=Mu^_sE_^hl48@rztub3*a1v0$lz>A(sl-h^fa@%^doarw5%9du60vQRS^%O)@H7ZR5"
    b"Q@@JmHP&FGw?*J2uh_r6dtlQkQPD`;)3*1Ni@h>F7j9Wh<#t?AtRsgA;{i23Q@Iuqj<QXZ)n80`G"
    b"!W2y>DoQ*!zY?h~77D@B`*)9gi5~0V-+8<>my1Gb{-;|M}OyvrLQx0h%Q~cc~fMK$_-57#dM1Mbi"
    b"{ANPQ>`Zp#(-jyVQLNhJb2XoP!J7UIGgic-HM3}O#l11rvhVH%3)I`R3<3_@1shjaAfhYx>sLJS2"
    b"inkl?4)yUT8@;{#=2^37cmbaZ#dSCUlzlCIh9UP5IspVw+!G;c|5aH%r3L*B6r4V56R0;v6V1plu"
    b"Py>Yx%W^ivtEKq^STbZ(EJ~}JwC=&7zkz&f7AL6><#Pd0TSKKYWAt$jM$c#hcAu7AK6>Cjwt!+Sj"
    b"^1<@3C?_XO6MEiP8No;cts$0OV+t>!K8*S^%G9AaFWz!o+WF`t+SSYT!ga~<jAscbO*%UlC@G;En"
    b"g|0Zs;&NIc{E~lVtBYIw|)4qmyEABB788(2~p`L_q<9^RSf0hehIdmOLNh#txw)iM9m{3c(wu|9~"
    b"{_ZRb4A^D>8oiVDLtTa-$P_$)-~ja&ksev43;rhjZ36pIM9Q$}%*=-_`QWX%Ja)U8VHg>P*Qt+|6"
    b"iNDd(SYCTLe>>W4zRtU>%d<OBnd-BTw{2^Q?asFEp!vA2RlZ#Jnc@2vD6fS9;c71+BZ&2QGNy5n="
    b"y`78OYYZ*9qP{HdP^y4$<)u3WmD}Xz8ijoFcXCO%!@|16{&XP>s@&E<X5>?DDo0sMO6<KO6L@cX$"
    b"0Z7v7U(a)Mph#Fb8Z@wo4?U1%ph~{r%~jNzjt&bBjA|`^vfH@bP-=BOu_DsRM>eEcE9nt0W8ux0|"
    b"JwqGmJU4JMv?4&dpLw&~qR-aOoiz^OD^(f|0@($z6fdM?01WomZQor}v*TM#CRi>pxW!++NHK?3z"
    b"!&ntHKfqn8-(nCQ8WEm-!ShNZ+5w--P9G>SIoD-x5?-B|OHWNWQ8_zet>s35qdaD##+=((!@b4G%"
    b"QhIt2Qp$#0M8Fl|&2Q44I1Z)<TA%*81)q~d?mUn!BA~PhjE6R+Wf4)LA+VN$K=98OLf+dULE{h8E"
    b"{jupwo;g*<mGK&}`!NdE{*E<@Bbp%~_>eepK>^eV=c8WN8rf|EB{5_r*cDv)pc$WM!Y6c-1}O=Z7"
    b"*(l-iG*lT22Xd?aL;75Lg0;Q2osYGD}&RXt_1?8e0_{Rr$c{SqCbO?W0c))X&*Nf!nX>S8M#95cP"
    b"m(i;165c^}*my*YR6Go{f0Y@wi{@TmivNvGO_3Y<|S&&rH4FO3PP3x=y1|IfOp+#yH&(QC9Yoio9"
    b"leN!mqMk=F>_80JD@V+LszqFiVroYyc7OJ*%%tO{&|?;{lS7;5$w5z0h1!uTPb0dKRTB@zvV>o#Y"
    b")MIk&2i@SVEu-&pdOG=B{2MV8Rbtf(wIal9X5}$#7ct(APy2q;Y&dayFuBjF^w(yO`x3U*JUHRS9"
    b"PA*s#Zh1kIGlV{}BI(s4DeWa~`R&!1-LWz<hx%GDBek!1#`<!goky`MKJ!Y77oWDy<WOOYQ$g^^Y"
    b"OgE$mWJ4@zRrdW&JgHXnW9ULZPAm*I-1A2IyalgD#~12PjaZk1y7N6&`^imr9!vWe7zdIp5_Gu`-"
    b")-RX3pn$oGbY83f8A!6K+(L@zu#V3D03Ip0X~|QydC9BL3JXGu&v7A|;mhrUO4sHX|Lt`>L+}w)Y"
    b"%b8scW{T26|~!r3Kbn&{6EP(8!Y;|N($WroJJzTBl^rB2%kiN4l!jmWlr&?+i@{$mlDWkw?S3z_3"
    b"7U--V`tK>T9$E{TCd+kZ<_KRT3DBQ<320Sgcp4QsV4QnfRL0TK?N!kRsFRcZD+hV&llv0r`K+S6I"
    b")?ik|wE(dwx?2M&5!eFEyzp)fWmTSO0opiasi^{`rSdhJGr}{(QMM5HZMTIlixJ-zQSuZwM!PSc*"
    b"Fs-Z4N~}@`DUj%Y+F#lKTpE^1;H01P+dTFQ2!l?<}`Ro_*LsUvRD5NpC89GiTGB3XBP4)2A9REe1"
    b"+a>9!P(a#0+g_D@H5W^c~SP<SFBwWdex~TxKbRYL37(;QTg;?&axl+0aF{*GailUY3edMKXBh6!x"
    b"{x3a%o_Pw7Uf41<QBL+vh1pR5V&?z-Ze9(jKLQWQrCOG9%CL`U-2VS++!rq9c*xR}APC#MOb`t>$"
    b">O>qs|;R<im4;8g*oiliHUJqA306Y;e-JH7?RyN|aipo=lCt0M}j{&lKPQw|0FYI=;32@~$BhgEE"
    b"V}Et&^F#!)k-463lco7;LsFQ3z&=hICy|Z`Y&8v+c)aGP4eTz^SKZl)jr*K~YHHTfuue(KdKP9Js"
    b"G|jBh%SlV|C)7u5yI0}o-bqIYIfa$sNEY@9qOCdm!@J8dX4Z7J4Z0v%BaHDE`0KxurCYn3>+@`gp"
    b";Sg@dIq%#(ZP9@y<`MBiZ-KGV>?H&6lw8U){Jg+6q}Mx2y7=lCVa>18WQXN>omv9))`rqp)@GQw>"
    b">g6bfaK_we_lMwGwWXcum5M=Z4p`W7na+pYR4*%fw?vMh}AFbPUFy1Ei9o$C1++E}PI3$h|8js=I"
    b"w@nVA;a!iM?=OWiuGH6>G=ruqy4V?00Jq)F^S_7)-I7t&Pq%6;{aO7F<BsLk;=@ce9k-=FSXj5$A"
    b"2?C(!vWHU};KnP0p#fujtEG!-3r{e_44Vz3pJ})}<0lWSo=6Fm25Q@bWu0c1iYpcJDTLQz$&~mIF"
    b"3l=AuA>r36HlX*zTM6-<8UEn?{$^&Gz>k5ElEb2JGIB5^85|2BQhVuYpl2?&HcjZP?@UdfE~z|h2"
    b"LSZbea>;hp?|0#+auYtYmFGwN4Z^-mqf0go6&ok0f{^MeT`yKD((*OF6hln(rFiW6&rMEE;%0eOT"
    b"Crn58|1I`-uYdkpmpeJ$!G-$z&@NzTK+*>U8%C=Z`u8TtQrDW-w&f0v$^)Ht(jpWDFnGP2E>gl2s"
    b"8*^*C<F=<c!Q)@!Lr`tjiU-@}0{u60oN4Q}t&He<;7{{@Oj(loDcyBD2?!8L|!qQovn`~P*Y}PON"
    b"3P*uCZvko<_ZjS2^L4l{g~i$f!fn*|>H1Zw``Q_{e2dkw8Mn*(>Xma+e#=kUE0H_H_G+rT?_wp(^"
    b"wr9$y1lJeo{luo`!5FlCYf$@$iXkK-H{J!+KS~SrQ9oJmvYOOUCO9R<t?|b##UyO!Tex`2+OU~Gg"
    b"_s~i(GAVt@w5>%>TlhkFbtpe_l-9{e7!&GJMtC^daYUbJK>U*G=u(iCQZE$mWQ)dWY<c7>(9&(x1"
    b"3>TpF74G*kAJJL2Yt@3`VtJXiy|<}@A^XcF4N-ELB<Jfg4Nq_*%)Vf!}fa^LD!XCLf&67TL6uR`("
    b"~Y;~)I*?zU<T{PJfHfY?Z%`1`Jh$egDY0wCHfdiuLQ#MBIj;fN#n0suAv}l?vbnGWwMlk6E4X{}4"
    b"K`hO5=Oq-_owu|z;8q&s-+2n*fK<08m9H)COKYYK*oFZo)6Uz$R*}{a8(R|Bo>D{G73PAhQeofXV"
    b"4d@{7<Ww2D$*KZJB{P?RH{~>?F(y!>?4757g_?gC(Fss_6zv!fM6aUYYhnd4T>&o-=xieu(UXs%A"
    b"gFvg_~omNNb3#^x-z3?Fw^2wm*>~c(6IFISdCvP^|}S>%Yx$?a68atMuOHsCGqJzs{{FPJ1@zt9+"
    b"nA{xzTTghgrNT#Qwrs(k5NF7sLVoUsHp4Z`YXdvxR?pM}j=Sg~r4NJZMSaDeT2U<*;u9uKKR!-+c"
    b"jH$(I<R>*7EtAu|hV2l!BXL0_0juuWS*5ic<rRg>7Gj+vWe*d*y*lsU*sQ338@sIB*e5UyWOJ7rF"
    b"(@4R<;`rsLIHh2p%g|oQd)nNYccJ%_zFNP|SjP8Bc&`N`n&Uo_VPhn1ZTs)3yK*1&dv)i!cjXG>N"
    b"V9L=gypzJEN2w4+CAAb15u5d`SaE|@2J11jniw0)3e9P&t}@x@7iA)BK^f4=`|dv2+6QtYcv@&#5"
    b"oXf_K)=5LO1X>GVgo$j{j8wQ@Y%0z%hP=!!vKF@`QU+*Y=JYgAvz=V23V$xnr(+>!60VdMbZDu7M"
    b"Dam`93(3`a?@zE{2@Z`7mLVyE8F4T5j|`TnLZn!Z_Q`Z2KY;0k%*@M`q!aZ{Yf_Bco69@iRHdV{7"
    b"YT?Q7&s4kYvdO(LwfeuYT#n=6PFv44gHma|0q(hzh8Vo&}i#^>%#oHe{rY1elN~ym~{@Fu?_6F82"
    b"+_SF+jXs>6=c*c>hc$*3<JME1t7dR|W;j{{E2LNt*rrXQ29L<v^IAde**mfHEMMoo@3#WGZ?9~Hf"
    b"%I*8neFGe6-vj?N6E^*2Cc9fwC5F;1~zO3_s}%21Pc~qp5VxJCMN&RWVVM~JR(W_0A>C2t+x9@M*"
    b"It%Grv;&9x2~F6em;p;f7z~<jyZ_szYdh2FwVpEARUEE7OS4-l;T&wu*;aRaQ^kDe}EwJ0RWr{G7"
    b"sj8zH;^5Mu+EK?5!_MSE6ECC9M{GjQ;AW#1RxA2#&GGomey9jSudJx=7sffjFcR)I>-c6oWcNNEO"
    b"@<Ah!u>~`Y3iuNnX7IGZWS|!B$!;|z233l*zx1tI;eD>{P{y7oJ`7npV!|EGEQYs@HTC!2D3aP{%"
    b"IDOcu9`i4Cw@kkj`?B<_-_Y8_37gp;tS#A=d@i(I>c&*hf%P^2I(z#zUy5ym`Oq;hl8wAM!1S|Y+"
    b"35-vL$KHG(B;ZQlJ!(*SfxLnbqC4>zXbJa3RMAU%%$qE&V;@M<7zHe0cV?()gitk`$hO8v$5MGd3"
    b"DH_a;>*tX^6jfB(A872YW~ON{8^uNg@)3^lR*|e0qAGV}?>BQTAjlLX{}=73-$Ruv*oPDD=Q}qf2"
    b"tK1gurfY(>6ey%Y&rtC|sowxJtgZcwM3_x59{DK#vzLW5e4+Z|Ke=ec_@pPZ}o<UKuEn}{koO#Cp"
    b"k)6>2qD=?@WU)NkIdq<%knz`(p{U%q6>Hx#$x{;qLe`qSozT<qo|M4Y}i0s79=IW`Q;;;E6bUoed"
    b"Ed<Dqh1gkw(Jq=4A9ko{3BK~Srs1WJU|aq&`@>-|=QR+Qe0N!-p03ASA@%^D1r}d~etqNz7K3TVI"
    b"s1gm{{__#_<_dw6;l;IdoS*-QSkjt7GTKP=PGophtIn3va=hZy7qET8B5kNp4-eOSS-@3<vtnLo^"
    b"+3bhN{&pVI8i!vxJ91Hp?gA+={lzZUrBZ6&t5P>oCoyLBIX{FXE$8pa"
)


def _payload_size_kb() -> float:
    """Size of the embedded compressed payload (KB)."""
    return len(_PAYLOAD) / 1024.0


try:
    DATA = json.loads(zlib.decompress(base64.b85decode(_PAYLOAD)))
except (ValueError, zlib.error) as _e:
    raise ImportError("raw_craft: corrupted embedded payload (re-run compiler.py)") from _e
