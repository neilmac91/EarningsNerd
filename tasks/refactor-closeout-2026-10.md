# Hot-module refactor — execution and spend ledger

Programme implementation and release receipts complete. The refactor implementation queue and final Ratchet are complete. The last runtime deployment, X5, is healthy; Ratchet main CI verified zero paid evaluations and no runtime deployment.
Public PR, comment and run links identify the evidence; key facts remain inline
when retained Actions artifacts expire.

## Spend ledger

Known telemetry estimate USD 3.815166 + unknown-call hold USD 0.553850
+ open reservations USD 0 = USD 4.369016 / USD 18.
Unencumbered programme USD 13.630984; wallet floor USD 5. Latest retained
balance USD 17.97 at 2026-10-11T02:47:28.4876132Z, [38106280469](https://github.com/neilmac91/EarningsNerd/actions/runs/38106280469).
After all current open reservations: USD 17.97.
This subtraction is not another provider reading. Interim readings retain their
classification. Wave 0 USD 0.133491 is counted once, including cancelled billed calls.

| Stage | PR | Known USD | Cumulative USD | Released USD | Retained stage hold USD |
|---|---|---|---|---|---|
| Dead | [1186](https://github.com/neilmac91/EarningsNerd/pull/1186) | 0.183549 | 0.317040 | 0.606451 | 0.000000 |
| I1 | [1187](https://github.com/neilmac91/EarningsNerd/pull/1187) | 0.183870 | 0.500910 | 0.606130 | 0.000000 |
| O1 | [1189](https://github.com/neilmac91/EarningsNerd/pull/1189) | 0.184464 | 0.685374 | 0.605536 | 0.000000 |
| T1 | [1193](https://github.com/neilmac91/EarningsNerd/pull/1193) | 0.182412 | 0.867786 | 0.607588 | 0.000000 |
| X1 | [1194](https://github.com/neilmac91/EarningsNerd/pull/1194) | 0.184985 | 1.052771 | 0.605015 | 0.000000 |
| C1 | [1196](https://github.com/neilmac91/EarningsNerd/pull/1196) | 0.185647 | 1.238418 | 0.604353 | 0.000000 |
| F1 | [1198](https://github.com/neilmac91/EarningsNerd/pull/1198) | 0.181051 | 1.419469 | 0.608949 | 0.000000 |
| O2 | [1201](https://github.com/neilmac91/EarningsNerd/pull/1201) | 0.183968 | 1.603437 | 0.606032 | 0.000000 |
| T2 | [1204](https://github.com/neilmac91/EarningsNerd/pull/1204) | 0.183839 | 1.787276 | 0.606161 | 0.000000 |
| T3 | [1205](https://github.com/neilmac91/EarningsNerd/pull/1205) | 0.184718 | 1.971994 | 0.605282 | 0.000000 |
| T4 | [1209](https://github.com/neilmac91/EarningsNerd/pull/1209) | 0.182975 | 2.154969 | 0.053175 | 0.553850 |
| F2 | [1210](https://github.com/neilmac91/EarningsNerd/pull/1210) | 0.184332 | 2.339301 | 0.605668 | 0.000000 |
| X2 | [1211](https://github.com/neilmac91/EarningsNerd/pull/1211) | 0.183492 | 2.522793 | 0.606508 | 0.000000 |
| C2 | [1212](https://github.com/neilmac91/EarningsNerd/pull/1212) | 0.186649 | 2.709442 | 0.603351 | 0.000000 |
| F3 | [1214](https://github.com/neilmac91/EarningsNerd/pull/1214) | 0.184866 | 2.894308 | 0.605134 | 0.000000 |
| X3 | [1215](https://github.com/neilmac91/EarningsNerd/pull/1215) | 0.183633 | 3.077941 | 0.606367 | 0.000000 |
| C3 | [1216](https://github.com/neilmac91/EarningsNerd/pull/1216) | 0.181431 | 3.259372 | 0.608569 | 0.000000 |
| F4 | [1217](https://github.com/neilmac91/EarningsNerd/pull/1217) | 0.185332 | 3.444704 | 0.604668 | 0.000000 |
| X4 | [1218](https://github.com/neilmac91/EarningsNerd/pull/1218) | 0.186639 | 3.631343 | 0.603361 | 0.000000 |
| X5 | [1219](https://github.com/neilmac91/EarningsNerd/pull/1219) | 0.183823 | 3.815166 | 0.606177 | 0.000000 |

| Stage / PR | Reviewed head | Run / surface | Reserved USD | Known USD |
|---|---|---|---|---|
| Dead [1186](https://github.com/neilmac91/EarningsNerd/pull/1186) | 316ad610f9dff0899829f8477f3e393a5f81c712 | [38058668924](https://github.com/neilmac91/EarningsNerd/actions/runs/38058668924) / summary | 0.73 | 0.176387 |
| Dead [1186](https://github.com/neilmac91/EarningsNerd/pull/1186) | 316ad610f9dff0899829f8477f3e393a5f81c712 | [38058722556](https://github.com/neilmac91/EarningsNerd/actions/runs/38058722556) / copilot | 0.06 | 0.007162 |
| I1 [1187](https://github.com/neilmac91/EarningsNerd/pull/1187) | d25bbe9ad61f43e179ee03631655d572f8f91b3f | [38060916011](https://github.com/neilmac91/EarningsNerd/actions/runs/38060916011) / summary | 0.73 | 0.176741 |
| I1 [1187](https://github.com/neilmac91/EarningsNerd/pull/1187) | d25bbe9ad61f43e179ee03631655d572f8f91b3f | [38060964981](https://github.com/neilmac91/EarningsNerd/actions/runs/38060964981) / copilot | 0.06 | 0.007129 |
| O1 [1189](https://github.com/neilmac91/EarningsNerd/pull/1189) | 218371e7209fe9beca84be1cedbbf48456a168c8 | [38064385182](https://github.com/neilmac91/EarningsNerd/actions/runs/38064385182) / summary | 0.73 | 0.177515 |
| O1 [1189](https://github.com/neilmac91/EarningsNerd/pull/1189) | 218371e7209fe9beca84be1cedbbf48456a168c8 | [38064443892](https://github.com/neilmac91/EarningsNerd/actions/runs/38064443892) / copilot | 0.06 | 0.006949 |
| T1 [1193](https://github.com/neilmac91/EarningsNerd/pull/1193) | 1e2a79da44c1c55a58a06c505ba061abe40106c9 | [38069785899](https://github.com/neilmac91/EarningsNerd/actions/runs/38069785899) / summary | 0.73 | 0.175639 |
| T1 [1193](https://github.com/neilmac91/EarningsNerd/pull/1193) | 1e2a79da44c1c55a58a06c505ba061abe40106c9 | [38069845623](https://github.com/neilmac91/EarningsNerd/actions/runs/38069845623) / copilot | 0.06 | 0.006773 |
| X1 [1194](https://github.com/neilmac91/EarningsNerd/pull/1194) | 44873d3c096d382dc96429e37032af81ac8c8da2 | [38072539805](https://github.com/neilmac91/EarningsNerd/actions/runs/38072539805) / summary | 0.73 | 0.178378 |
| X1 [1194](https://github.com/neilmac91/EarningsNerd/pull/1194) | 44873d3c096d382dc96429e37032af81ac8c8da2 | [38072600048](https://github.com/neilmac91/EarningsNerd/actions/runs/38072600048) / copilot | 0.06 | 0.006607 |
| C1 [1196](https://github.com/neilmac91/EarningsNerd/pull/1196) | f251d3d0e2d9ce009ec6136c12008568c821158c | [38078342422](https://github.com/neilmac91/EarningsNerd/actions/runs/38078342422) / summary | 0.73 | 0.178779 |
| C1 [1196](https://github.com/neilmac91/EarningsNerd/pull/1196) | f251d3d0e2d9ce009ec6136c12008568c821158c | [38078392189](https://github.com/neilmac91/EarningsNerd/actions/runs/38078392189) / copilot | 0.06 | 0.006868 |
| F1 [1198](https://github.com/neilmac91/EarningsNerd/pull/1198) | 37433c603994b8f78316497be0af2d3a585dbb8c | [38080854994](https://github.com/neilmac91/EarningsNerd/actions/runs/38080854994) / summary | 0.73 | 0.174486 |
| F1 [1198](https://github.com/neilmac91/EarningsNerd/pull/1198) | 37433c603994b8f78316497be0af2d3a585dbb8c | [38080887181](https://github.com/neilmac91/EarningsNerd/actions/runs/38080887181) / copilot | 0.06 | 0.006565 |
| O2 [1201](https://github.com/neilmac91/EarningsNerd/pull/1201) | c3206afbf4a03c13aa73e8530f1ec75d4e70d3b0 | [38084643984](https://github.com/neilmac91/EarningsNerd/actions/runs/38084643984) / summary | 0.73 | 0.176966 |
| O2 [1201](https://github.com/neilmac91/EarningsNerd/pull/1201) | c3206afbf4a03c13aa73e8530f1ec75d4e70d3b0 | [38084690123](https://github.com/neilmac91/EarningsNerd/actions/runs/38084690123) / copilot | 0.06 | 0.007002 |
| T2 [1204](https://github.com/neilmac91/EarningsNerd/pull/1204) | e12c7b953d8e116d9c437a9f8a24d8fa8ae58cb7 | [38086536136](https://github.com/neilmac91/EarningsNerd/actions/runs/38086536136) / summary | 0.73 | 0.177544 |
| T2 [1204](https://github.com/neilmac91/EarningsNerd/pull/1204) | e12c7b953d8e116d9c437a9f8a24d8fa8ae58cb7 | [38086570238](https://github.com/neilmac91/EarningsNerd/actions/runs/38086570238) / copilot | 0.06 | 0.006295 |
| T3 [1205](https://github.com/neilmac91/EarningsNerd/pull/1205) | 5b70c38fdd68c71894a70176665d65f3e1bad53c | [38089540400](https://github.com/neilmac91/EarningsNerd/actions/runs/38089540400) / summary | 0.73 | 0.178061 |
| T3 [1205](https://github.com/neilmac91/EarningsNerd/pull/1205) | 5b70c38fdd68c71894a70176665d65f3e1bad53c | [38089579609](https://github.com/neilmac91/EarningsNerd/actions/runs/38089579609) / copilot | 0.06 | 0.006657 |
| T4 [1209](https://github.com/neilmac91/EarningsNerd/pull/1209) | 8aa9f806d954cdea9303353104d9081ff53ab4df | [38094895509](https://github.com/neilmac91/EarningsNerd/actions/runs/38094895509) / summary | 0.73 | 0.176150 |
| T4 [1209](https://github.com/neilmac91/EarningsNerd/pull/1209) | 8aa9f806d954cdea9303353104d9081ff53ab4df | [38094905334](https://github.com/neilmac91/EarningsNerd/actions/runs/38094905334) / copilot | 0.06 | 0.006825 |
| F2 [1210](https://github.com/neilmac91/EarningsNerd/pull/1210) | a5fc18408165f2df87a1015fdeb5183c8376616c | [38096049379](https://github.com/neilmac91/EarningsNerd/actions/runs/38096049379) / summary | 0.73 | 0.177818 |
| F2 [1210](https://github.com/neilmac91/EarningsNerd/pull/1210) | a5fc18408165f2df87a1015fdeb5183c8376616c | [38096080765](https://github.com/neilmac91/EarningsNerd/actions/runs/38096080765) / copilot | 0.06 | 0.006514 |
| X2 [1211](https://github.com/neilmac91/EarningsNerd/pull/1211) | 35d73c3fe2d10b04d60e511a4513b48f13fc948b | [38097399619](https://github.com/neilmac91/EarningsNerd/actions/runs/38097399619) / summary | 0.73 | 0.176477 |
| X2 [1211](https://github.com/neilmac91/EarningsNerd/pull/1211) | 35d73c3fe2d10b04d60e511a4513b48f13fc948b | [38097411344](https://github.com/neilmac91/EarningsNerd/actions/runs/38097411344) / copilot | 0.06 | 0.007015 |
| C2 [1212](https://github.com/neilmac91/EarningsNerd/pull/1212) | 48deb262b266188b90f68f715275e844573b205f | [38098311426](https://github.com/neilmac91/EarningsNerd/actions/runs/38098311426) / summary | 0.73 | 0.179631 |
| C2 [1212](https://github.com/neilmac91/EarningsNerd/pull/1212) | 48deb262b266188b90f68f715275e844573b205f | [38098367123](https://github.com/neilmac91/EarningsNerd/actions/runs/38098367123) / copilot | 0.06 | 0.007018 |
| F3 [1214](https://github.com/neilmac91/EarningsNerd/pull/1214) | 1426595698cd14cd671f4e142f3b1f3eb64fcbc6 | [38100217671](https://github.com/neilmac91/EarningsNerd/actions/runs/38100217671) / summary | 0.73 | 0.178336 |
| F3 [1214](https://github.com/neilmac91/EarningsNerd/pull/1214) | 1426595698cd14cd671f4e142f3b1f3eb64fcbc6 | [38100264870](https://github.com/neilmac91/EarningsNerd/actions/runs/38100264870) / copilot | 0.06 | 0.006530 |
| X3 [1215](https://github.com/neilmac91/EarningsNerd/pull/1215) | e85104391ec82a47763385bd3526b1661ab9b292 | [38101181396](https://github.com/neilmac91/EarningsNerd/actions/runs/38101181396) / summary | 0.73 | 0.177484 |
| X3 [1215](https://github.com/neilmac91/EarningsNerd/pull/1215) | e85104391ec82a47763385bd3526b1661ab9b292 | [38101237630](https://github.com/neilmac91/EarningsNerd/actions/runs/38101237630) / copilot | 0.06 | 0.006149 |
| C3 [1216](https://github.com/neilmac91/EarningsNerd/pull/1216) | e61218e4342596c6ec7ccf157397e0317d235de5 | [38102130269](https://github.com/neilmac91/EarningsNerd/actions/runs/38102130269) / summary | 0.73 | 0.175112 |
| C3 [1216](https://github.com/neilmac91/EarningsNerd/pull/1216) | e61218e4342596c6ec7ccf157397e0317d235de5 | [38102208316](https://github.com/neilmac91/EarningsNerd/actions/runs/38102208316) / copilot | 0.06 | 0.006319 |
| F4 [1217](https://github.com/neilmac91/EarningsNerd/pull/1217) | 0b5708de028d592781621327dc4b0c3a7274f00b | [38103192299](https://github.com/neilmac91/EarningsNerd/actions/runs/38103192299) / summary | 0.73 | 0.178265 |
| F4 [1217](https://github.com/neilmac91/EarningsNerd/pull/1217) | 0b5708de028d592781621327dc4b0c3a7274f00b | [38103228805](https://github.com/neilmac91/EarningsNerd/actions/runs/38103228805) / copilot | 0.06 | 0.007067 |
| X4 [1218](https://github.com/neilmac91/EarningsNerd/pull/1218) | bbc7c89298a49cad3cf0b2f35d310865c0545ea0 | [38104095562](https://github.com/neilmac91/EarningsNerd/actions/runs/38104095562) / summary | .73 | 0.179568 |
| X4 [1218](https://github.com/neilmac91/EarningsNerd/pull/1218) | bbc7c89298a49cad3cf0b2f35d310865c0545ea0 | [38104164894](https://github.com/neilmac91/EarningsNerd/actions/runs/38104164894) / copilot | .06 | 0.007071 |
| X5 [1219](https://github.com/neilmac91/EarningsNerd/pull/1219) | abc3fe84d9f9d11871e67072cad4ab9adfb850aa | [38105052375](https://github.com/neilmac91/EarningsNerd/actions/runs/38105052375) / summary | .73 | 0.177040 |
| X5 [1219](https://github.com/neilmac91/EarningsNerd/pull/1219) | abc3fe84d9f9d11871e67072cad4ab9adfb850aa | [38105083546](https://github.com/neilmac91/EarningsNerd/actions/runs/38105083546) / copilot | .06 | 0.006783 |

## Original Wave 0 trigger rows

| UTC | PR | Head | Run | Original result / calls | Estimated USD | Wave 0 cumulative USD |
|---|---|---|---|---|---|---|
| 2026-10-09 11:58:43 | #1156 | `6ba7f9c9` | [37927066597](https://github.com/neilmac91/EarningsNerd/actions/runs/37927066597) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:16:30 | #1157 | `21f06939` | [37928960239](https://github.com/neilmac91/EarningsNerd/actions/runs/37928960239) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:19:11 | #1158 | `834c2c36` | [37929240128](https://github.com/neilmac91/EarningsNerd/actions/runs/37929240128) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:24:03 | #1159 | `53c1dd85` | [37929772958](https://github.com/neilmac91/EarningsNerd/actions/runs/37929772958) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:26:43 | #1160 | `fc1f2c06` | [37930064650](https://github.com/neilmac91/EarningsNerd/actions/runs/37930064650) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:29:20 | #1161 | `7335e225` | [37930350928](https://github.com/neilmac91/EarningsNerd/actions/runs/37930350928) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:30:59 | #1162 | `d8a6446d` | [37930544123](https://github.com/neilmac91/EarningsNerd/actions/runs/37930544123) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:50:12 | #1156 | `f29cde2e` | [37932659957](https://github.com/neilmac91/EarningsNerd/actions/runs/37932659957) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 16:39:36 | #1157 | `13c3da14` | [37960700910](https://github.com/neilmac91/EarningsNerd/actions/runs/37960700910) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 16:40:20 | #1161 | `48e2f7cd` | [37960789051](https://github.com/neilmac91/EarningsNerd/actions/runs/37960789051) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 16:43:46 | #1158 | `834c2c36` | [37961202125](https://github.com/neilmac91/EarningsNerd/actions/runs/37961202125) | success, 36 | 0.006767 | 0.006767 |
| 2026-10-09 16:44:20 | #1159 | `53c1dd85` | [37961270283](https://github.com/neilmac91/EarningsNerd/actions/runs/37961270283) | success, 37 | 0.006948 | 0.013715 |
| 2026-10-09 16:44:57 | #1160 | `fc1f2c06` | [37961341507](https://github.com/neilmac91/EarningsNerd/actions/runs/37961341507) | success, 35 | 0.006584 | 0.020299 |
| 2026-10-09 16:45:27 | #1162 | `d8a6446d` | [37961405715](https://github.com/neilmac91/EarningsNerd/actions/runs/37961405715) | success, 36 | 0.006707 | 0.027006 |
| 2026-10-09 16:46:10 | #1156 | `f29cde2e` | [37961491439](https://github.com/neilmac91/EarningsNerd/actions/runs/37961491439) | success, 35 | 0.006494 | 0.033500 |
| 2026-10-09 16:51:01 | #1158 | `0450017c` | [37962060704](https://github.com/neilmac91/EarningsNerd/actions/runs/37962060704) | success, 34 | 0.006456 | 0.039956 |
| 2026-10-09 16:52:24 | #1157 | `13c3da14` | [37962221057](https://github.com/neilmac91/EarningsNerd/actions/runs/37962221057) | success, 38 | 0.007017 | 0.046973 |
| 2026-10-09 16:52:26 | #1161 | `48e2f7cd` | [37962225333](https://github.com/neilmac91/EarningsNerd/actions/runs/37962225333) | success, 35 | 0.006476 | 0.053449 |
| 2026-10-09 16:56:26 | #1160 | `493be74f` | [37962694400](https://github.com/neilmac91/EarningsNerd/actions/runs/37962694400) | success, 36 | 0.006884 | 0.060333 |
| 2026-10-09 16:56:28 | #1162 | `6e2901f4` | [37962697079](https://github.com/neilmac91/EarningsNerd/actions/runs/37962697079) | success, 37 | 0.007053 | 0.067386 |
| 2026-10-09 17:29:46 | #1156 | `f29cde2e` | [37966670586](https://github.com/neilmac91/EarningsNerd/actions/runs/37966670586) | cancelled, 35; accidental reopen | 0.006525 | 0.073911 |
| 2026-10-09 17:31:31 | #1156 | `0f9e9813` | [37966887344](https://github.com/neilmac91/EarningsNerd/actions/runs/37966887344) | success, 35 | 0.006715 | 0.080626 |
| 2026-10-09 17:36:33 | #1157 | `fe70d7fd` | [37967479957](https://github.com/neilmac91/EarningsNerd/actions/runs/37967479957) | success, 37 | 0.006860 | 0.087486 |
| 2026-10-09 17:36:35 | #1161 | `24bc462a` | [37967484361](https://github.com/neilmac91/EarningsNerd/actions/runs/37967484361) | success, 35 | 0.006501 | 0.093987 |
| 2026-10-09 17:51:20 | #1156 | `302ffb8a` | [37969197119](https://github.com/neilmac91/EarningsNerd/actions/runs/37969197119) | success, 34 | 0.006423 | 0.100410 |
| 2026-10-09 17:56:25 | #1157 | `b787b8e2` | [37969790917](https://github.com/neilmac91/EarningsNerd/actions/runs/37969790917) | success, 38 | 0.007153 | 0.107563 |
| 2026-10-09 18:21:51 | #1156 | `dcd3e57e` | [37972749096](https://github.com/neilmac91/EarningsNerd/actions/runs/37972749096) | success, 36 | 0.006835 | 0.114398 |
| 2026-10-09 18:37:16 | #1156 | `0d4fbeb0` | [37974547301](https://github.com/neilmac91/EarningsNerd/actions/runs/37974547301) | success, 34 | 0.006344 | 0.120742 |
| 2026-10-09 18:53:33 | #1156 | `973bf07d` | [37976422204](https://github.com/neilmac91/EarningsNerd/actions/runs/37976422204) | success, 34 | 0.006413 | 0.127155 |
| 2026-10-09 19:07:49 | #1156 | `c8e45eb9` | [37978091846](https://github.com/neilmac91/EarningsNerd/actions/runs/37978091846) | success, 34 | 0.006336 | 0.133491 |

## Current final-stage disposition

| Stage | PR | Head | Disposition | CI | Codex | Merge | Main |
|---|---|---|---|---|---|---|---|
| F4 | [1217](https://github.com/neilmac91/EarningsNerd/pull/1217) | 0b5708de028d592781621327dc4b0c3a7274f00b | release verified | [38103192299](https://github.com/neilmac91/EarningsNerd/actions/runs/38103192299) / success | clean 2026-10-11T01:53:56.713476Z; exact-head review verified | 3038ccf694affe7343720bb51ee75f6631dbdb9a | [38104041389](https://github.com/neilmac91/EarningsNerd/actions/runs/38104041389) |
| X4 | [1218](https://github.com/neilmac91/EarningsNerd/pull/1218) | bbc7c89298a49cad3cf0b2f35d310865c0545ea0 | release verified | [38104095562](https://github.com/neilmac91/EarningsNerd/actions/runs/38104095562) / success | clean 2026-10-11T02:11:37.849696Z; exact-head review verified | 44107449957d1083601b80d729e6b7aed3198fd6 | [38104998916](https://github.com/neilmac91/EarningsNerd/actions/runs/38104998916) |
| X5 | [1219](https://github.com/neilmac91/EarningsNerd/pull/1219) | abc3fe84d9f9d11871e67072cad4ab9adfb850aa | release verified | [38105052375](https://github.com/neilmac91/EarningsNerd/actions/runs/38105052375) / success | clean 2026-10-11T02:27:22.221797Z; +1; no comments | 777ba27653c443d8f756553dd39bdc8950b694c6 | [38106052520](https://github.com/neilmac91/EarningsNerd/actions/runs/38106052520) |
| Ratchet | [1220](https://github.com/neilmac91/EarningsNerd/pull/1220) | f1152041eccc81ff94751387b661649fe916758b | merged; verified paid/deployment skips | [38106095026](https://github.com/neilmac91/EarningsNerd/actions/runs/38106095026) / success | clean 2026-10-11T02:45:30.877171Z; +1; no inline findings | 855daa3383ccf82896026dacfba13f7553619ce1 | [38106827847](https://github.com/neilmac91/EarningsNerd/actions/runs/38106827847) |

| Stage | Summary | Advisories | Original Copilot verdict | Triage | Paid source | Base / head / tree |
|---|---|---|---|---|---|---|
| F4 | 70 scored / errors 0 / hard-veto rate 0.0 | untraceable 1.5; citation 0.8146 | 17/18; accepted=false; errors=1; [38103228805](https://github.com/neilmac91/EarningsNerd/actions/runs/38103228805) | [triage](https://github.com/neilmac91/EarningsNerd/pull/1217#issuecomment-6104407810) | 61ce8ed46608d04f7f9de652c0cb6a0f6710528e | 82cd322e959d0951954d23474f300063384ab570 / 0b5708de028d592781621327dc4b0c3a7274f00b / c3f7253249563207edf4d6c5336a4f99c8a6eb9d |
| X4 | 70 scored / errors 0 / hard-veto rate 0.0 | untraceable 1.5; citation 0.8593 | 17/18; accepted=false; errors=1; [38104164894](https://github.com/neilmac91/EarningsNerd/actions/runs/38104164894) | [triage](https://github.com/neilmac91/EarningsNerd/pull/1218#issuecomment-6104504659) | c4fa9b2f21f4cad87d5726ebfdce6401c96c524e | 3038ccf694affe7343720bb51ee75f6631dbdb9a / bbc7c89298a49cad3cf0b2f35d310865c0545ea0 / 88bece328e7f006760a70229f917730d4ae5e3c4 |
| X5 | 70 scored / errors 0 / hard-veto rate 0.0 | untraceable 1.2143; citation 0.8513 | 18/18; accepted=true; errors=0; [38105083546](https://github.com/neilmac91/EarningsNerd/actions/runs/38105083546) | no triage exception recorded | 01561530f1347f3ec1407c002a3c4e2cf91bf5f6 | 44107449957d1083601b80d729e6b7aed3198fd6 / abc3fe84d9f9d11871e67072cad4ab9adfb850aa / 860a07be6af9953c63d9c617ad06cae01cbaebfa |
| Ratchet | all paid summary steps skipped | not applicable | Copilot not triggered | no paid draw | [verified zero-cost receipt](https://github.com/neilmac91/EarningsNerd/actions/runs/38106095026/job/114371839581) | f1152041eccc81ff94751387b661649fe916758b |

| Stage | Explicit skip | Head | Disposition | Public evidence |
|---|---|---|---|---|
| Ratchet | verified_paid_skip | f1152041eccc81ff94751387b661649fe916758b | All four paid summary steps skipped; no Copilot workflow for this head. | [receipt](https://github.com/neilmac91/EarningsNerd/actions/runs/38106095026/job/114371839581) |
| Ratchet | verified_release_skip | f1152041eccc81ff94751387b661649fe916758b | Main CI 38106827847 passed on 855daa3383ccf82896026dacfba13f7553619ce1; paid summary skipped, no Copilot; deployment detector skipped every mutating step. | [receipt](https://github.com/neilmac91/EarningsNerd/pull/1220#issuecomment-6104877831) |

F4 and X4 attributed red runs retain `accepted=false`: BABA
`viewed-native-revenue-2025` d1 was withheld in both generations for “Unverified or
ambiguous referenced citation”. Each linked triage records all 18 rows replayed on
that stage's clean exact main, exit 0, zero unexplained/mismatch/verdict disagreement,
and all other 17 passing. All five RUNBOOK conditions are recorded. No redraw.
Attribution does not replace CI/review/cost/release prerequisites.

## Earlier evaluations and integration context

| Stage | Summary / advisories | Copilot / source binding | Public evidence |
|---|---|---|---|
| Dead | 70/70 scored; hard gate passed; two retained advisory categories; not semantic acceptance | red; one named publication withhold; recorded RUNBOOK attribution | [triage](https://github.com/neilmac91/EarningsNerd/pull/1186#issuecomment-6098419786) |
| I1 | 70/70 scored; hard gate passed; two retained advisory categories; not semantic acceptance | 18/18 passed; zero errors | [1187](https://github.com/neilmac91/EarningsNerd/pull/1187) |
| O1 | 70/70 scored; hard gate passed; two retained advisory categories; not semantic acceptance | 18/18 passed; zero errors | [1189](https://github.com/neilmac91/EarningsNerd/pull/1189) |
| T1 | 70/70 scored; hard gate passed; two retained advisory categories; not semantic acceptance | 18/18 passed; zero errors | [1193](https://github.com/neilmac91/EarningsNerd/pull/1193) |
| X1 | 70/70 scored; hard gate passed; two retained advisory categories; not semantic acceptance | 18/18 passed; zero errors | [1194](https://github.com/neilmac91/EarningsNerd/pull/1194) |
| C1 | 70/70 scored; hard gate passed; two retained advisory categories; not semantic acceptance | 18/18 passed; zero errors | [1196](https://github.com/neilmac91/EarningsNerd/pull/1196) |
| F1 | 70/70 scored; hard gate passed; two retained advisory categories; not semantic acceptance | red; one named publication withhold; recorded RUNBOOK attribution | [triage](https://github.com/neilmac91/EarningsNerd/pull/1198#issuecomment-6101514137) |
| O2 | 70/70 scored; hard gate passed; two retained advisory categories; not semantic acceptance | 18/18 passed; zero errors | [1201](https://github.com/neilmac91/EarningsNerd/pull/1201) |
| T2 | 70/70 scored; hard gate passed; two retained advisory categories; not semantic acceptance | red; one named publication withhold; recorded RUNBOOK attribution | [triage](https://github.com/neilmac91/EarningsNerd/pull/1204#issuecomment-6102259480) |
| T3 | 70/70 scored; hard gate passed; two retained advisory categories; not semantic acceptance | 18/18 passed; zero errors | [1205](https://github.com/neilmac91/EarningsNerd/pull/1205) |
| F3 | 70 scored; errors 0; hard-veto rate 0.0; untraceable 1.4714; citation 0.8349 | accepted=true; source 55c758a3d369963cb4491723e92e28d8ec00aa05; tree 2843f395fde45906fcbc4fefbfd93237e68f814b | [1214](https://github.com/neilmac91/EarningsNerd/pull/1214) |
| X3 | 70 scored; errors 0; hard-veto rate 0.0; untraceable 1.4571; citation 0.8334 | accepted=true; source 9f5f5f2d6dfa02351b6edd27fb6b05f43627da4d; tree c78b83fca40518897e1c1a37321323b150fc96a1 | [1215](https://github.com/neilmac91/EarningsNerd/pull/1215) |
| C3 | 70 scored; errors 0; hard-veto rate 0.0; untraceable 1.0429; citation 0.8413 | accepted=true; source 87ea43a6f957ee7f53344bccc26cfb19f497fc35; tree 2fbab08d9832b6179c691c3f7023b09becf1bb7c | [1216](https://github.com/neilmac91/EarningsNerd/pull/1216) |

T4 and X2 keep their original 17/18 red verdicts and exact-main offline attribution
with zero unexplained rows; no paid redraw. T4's 71 logged summary calls include an
unknown-cost provider error before its successful retry: known summary USD 0.176150,
Copilot USD 0.006825, hold USD 0.553850, released USD 0.053175. The unknown actual cost
remains null. Wallet changes and report `total_cost_usd: 0.0` are not cost evidence.
[T4](https://github.com/neilmac91/EarningsNerd/pull/1209),
[X2 triage](https://github.com/neilmac91/EarningsNerd/pull/1211#issuecomment-6103639516).

X2 main 38098240615 attempt 1 failed delayed-wakeup timing: 6,736 passed, 39 skipped,
one failed; deployment skipped. Exactly one unpaid failed-job retry passed 6,737
tests with 39 skipped in 274.16s, plus two performance tests in 19.40s, then deployed
the reviewed X2 app. Tests-only
[PR 1213](https://github.com/neilmac91/EarningsNerd/pull/1213#issuecomment-6104058316)
merged `80119cd2de079cde08e0822f7e7b014edfb1a618`; main 38100044035 passed, paid summary
skipped, no Copilot, all mutating deployment steps skipped. Its committed mutation
gave four failures and four restored passes; pre-fix failures used the new caller-yield
control with the old patch, not a pristine baseline. All 61 assertions and 14 definitions were preserved;
the particular interfering task was not identified. [X2 release](https://github.com/neilmac91/EarningsNerd/pull/1211#issuecomment-6103914456).

C2's only paid draw remains USD 0.186649. Its actual merge tree
`1cb348d5dcd38c9703d0cfb8bf1e7dd96b56e4fa` matches the synthetic composition tested
on `b14fbe878938bd37b4aedbacfa9ffccf6cce7487` (6,737 passed, 39 skipped, 83.92s). App/evals/prompts/
workflows/requirements matched the paid C2 source; only the reviewed limiter test
was added. No second draw. F2's unrelated frontend-only main advance likewise
caused no paid redraw. [C2](https://github.com/neilmac91/EarningsNerd/pull/1212),
[F2](https://github.com/neilmac91/EarningsNerd/pull/1210).

C2's published appendix expands the actual phases and pins the original source
hash while reading only published BASE/HEAD. One committed real-file kind mutation
was rejected and restored; prompt/message bytes, async lifecycle and patch seams
were preserved. C3's standalone proof likewise reads only final published refs.
All strict-proof reruns on final refs are separate from carried full gates.
The original local execution heads/times remain provenance, never public-object
links or claims that the full suite reran on a later squash.

Tests-only [PR 1208](https://github.com/neilmac91/EarningsNerd/pull/1208)
head `7140c42542b69ff1a63fca66f40ca72e130f6272` has verified zero paid/deploy disposition:
[PR CI 38094319505, summary job 114336965838](https://github.com/neilmac91/EarningsNerd/actions/runs/38094319505/job/114336965838)
skipped all four paid-evaluation steps; no Copilot check. Main 38094830237 on exact
b3469e650b8488e7a66d2e6c405368f991b21407 passed. Its
[deploy job 114340334261](https://github.com/neilmac91/EarningsNerd/actions/runs/38094830237/job/114340334261)
ran the detector only; image, migration, worker, API, scheduled-job and health
steps skipped. The historical missing-receipt gap is closed; no paid row is invented.


## Verified releases

| Stage / PR | Reviewed head | Merge / tree | Main | Migrations | API / worker | Health UTC | Evidence |
|---|---|---|---|---|---|---|---|
| Dead [1186](https://github.com/neilmac91/EarningsNerd/pull/1186) | 316ad610f9dff0899829f8477f3e393a5f81c712 | b178561b5765517d614c479afff2d679419023fd / tree recorded in PR | [38059507826](https://github.com/neilmac91/EarningsNerd/actions/runs/38059507826) | applied=0 skipped=41 | earningsnerd-backend-00467-7n8 / earningsnerd-task-worker-00020-wqh | in release receipt | [verified](https://github.com/neilmac91/EarningsNerd/pull/1186#issuecomment-6098583983) |
| I1 [1187](https://github.com/neilmac91/EarningsNerd/pull/1187) | d25bbe9ad61f43e179ee03631655d572f8f91b3f | 88f014746b05fc254de30dfd8c70814f1fb8657d / tree recorded in PR | [38061726007](https://github.com/neilmac91/EarningsNerd/actions/runs/38061726007) | applied=0 skipped=41 | earningsnerd-backend-00468-4hc / earningsnerd-task-worker-00021-x2n | in release receipt | [verified](https://github.com/neilmac91/EarningsNerd/pull/1187#issuecomment-6098887598) |
| O1 [1189](https://github.com/neilmac91/EarningsNerd/pull/1189) | 218371e7209fe9beca84be1cedbbf48456a168c8 | fd61bd070eaecb2bcfcebf976f3f5dc58ab908b1 / tree recorded in PR | [38065243414](https://github.com/neilmac91/EarningsNerd/actions/runs/38065243414) | applied=0 skipped=41 | earningsnerd-backend-00469-rwr / earningsnerd-task-worker-00022-sql | in release receipt | [verified](https://github.com/neilmac91/EarningsNerd/pull/1189#issuecomment-6099418848) |
| T1 [1193](https://github.com/neilmac91/EarningsNerd/pull/1193) | 1e2a79da44c1c55a58a06c505ba061abe40106c9 | 26fa5f15a533c8ccc09949b77f784642c5858cc7 / tree recorded in PR | [38070633182](https://github.com/neilmac91/EarningsNerd/actions/runs/38070633182) | applied=0 skipped=43 | earningsnerd-backend-00471-nn8 / earningsnerd-task-worker-00024-5ww | in release receipt | [verified](https://github.com/neilmac91/EarningsNerd/pull/1193#issuecomment-6100170205) |
| X1 [1194](https://github.com/neilmac91/EarningsNerd/pull/1194) | 44873d3c096d382dc96429e37032af81ac8c8da2 | 97293e76fe71ff6b7e1848d57f00e808866e8c1c / tree recorded in PR | [38073410546](https://github.com/neilmac91/EarningsNerd/actions/runs/38073410546) | applied=0 skipped=43 | earningsnerd-backend-00472-nhx / earningsnerd-task-worker-00025-gjw | in release receipt | [verified](https://github.com/neilmac91/EarningsNerd/pull/1194#issuecomment-6100531867) |
| C1 [1196](https://github.com/neilmac91/EarningsNerd/pull/1196) | f251d3d0e2d9ce009ec6136c12008568c821158c | 3f999e3ca8e6a8d8150f1ca1edc5fde9e0caffa2 / tree recorded in PR | [38079161669](https://github.com/neilmac91/EarningsNerd/actions/runs/38079161669) | applied=0 skipped=43 | earningsnerd-backend-00473-nb5 / earningsnerd-task-worker-00026-wqr | in release receipt | [verified](https://github.com/neilmac91/EarningsNerd/pull/1196#issuecomment-6101297473) |
| F1 [1198](https://github.com/neilmac91/EarningsNerd/pull/1198) | 37433c603994b8f78316497be0af2d3a585dbb8c | 3d1e8b7436ac7de53100300b8be74a528e5d6573 / tree recorded in PR | [38081944741](https://github.com/neilmac91/EarningsNerd/actions/runs/38081944741) | applied=0 skipped=43 | earningsnerd-backend-00474-zcn / earningsnerd-task-worker-00027-q2q | in release receipt | [verified](https://github.com/neilmac91/EarningsNerd/pull/1198#issuecomment-6101681925) |
| O2 [1201](https://github.com/neilmac91/EarningsNerd/pull/1201) | c3206afbf4a03c13aa73e8530f1ec75d4e70d3b0 | a15eae70fceabcaba5b7d2077d2a0a8e9d262d0e / tree recorded in PR | [38085409832](https://github.com/neilmac91/EarningsNerd/actions/runs/38085409832) | applied=0 skipped=43 | earningsnerd-backend-00475-629 / earningsnerd-task-worker-00028-9kw | in release receipt | [verified](https://github.com/neilmac91/EarningsNerd/pull/1201#issuecomment-6102122105) |
| T2 [1204](https://github.com/neilmac91/EarningsNerd/pull/1204) | e12c7b953d8e116d9c437a9f8a24d8fa8ae58cb7 | a74df3b2bc5a088f8983476d4f375cce1096ddf6 / tree recorded in PR | [38087323127](https://github.com/neilmac91/EarningsNerd/actions/runs/38087323127) | applied=0 skipped=43 | earningsnerd-backend-00476-p6p / earningsnerd-task-worker-00029-4rw | in release receipt | [verified](https://github.com/neilmac91/EarningsNerd/pull/1204#issuecomment-6102382297) |
| T3 [1205](https://github.com/neilmac91/EarningsNerd/pull/1205) | 5b70c38fdd68c71894a70176665d65f3e1bad53c | df13b42a3c75e1835a043a6668fcf34c12d19034 / tree recorded in PR | [38090345343](https://github.com/neilmac91/EarningsNerd/actions/runs/38090345343) | applied=0 skipped=43 | earningsnerd-backend-00477-29j / earningsnerd-task-worker-00030-jj9 | in release receipt | [verified](https://github.com/neilmac91/EarningsNerd/pull/1205#issuecomment-6102814590) |
| T4 [1209](https://github.com/neilmac91/EarningsNerd/pull/1209) | 8aa9f806d954cdea9303353104d9081ff53ab4df | c0795fd49e429b2cc6586e33e69b4f169ddbafc2 / 4a22f83af965d03af2267779f9975cd675500775 | [38095913192](https://github.com/neilmac91/EarningsNerd/actions/runs/38095913192) | applied=0 skipped=43 | earningsnerd-backend-00478-nch / earningsnerd-task-worker-00031-2ls | 2026-10-10 23:53:39 UTC | [verified](https://github.com/neilmac91/EarningsNerd/pull/1209#issuecomment-6103501945) |
| F2 [1210](https://github.com/neilmac91/EarningsNerd/pull/1210) | a5fc18408165f2df87a1015fdeb5183c8376616c | 51ee4aee9fb8b64d68ff34f0abd99eadce0ab566 / 9b900a96cb6ebc0602ddff0d8b543937fb0d0289 | [38097256487](https://github.com/neilmac91/EarningsNerd/actions/runs/38097256487) | applied=0 skipped=43 | earningsnerd-backend-00479-gsw / earningsnerd-task-worker-00032-srs | 2026-10-11 00:21:30 UTC | [verified](https://github.com/neilmac91/EarningsNerd/pull/1210#issuecomment-6103709720) |
| X2 [1211](https://github.com/neilmac91/EarningsNerd/pull/1211) | 35d73c3fe2d10b04d60e511a4513b48f13fc948b | a468c5c32a27b8b22440903dd8e41139abf27594 / 0f1c576907475e7a732b59f599ec2ae09c59bec7 | [38098240615](https://github.com/neilmac91/EarningsNerd/actions/runs/38098240615) | applied=0 skipped=43 | earningsnerd-backend-00480-4vr / earningsnerd-task-worker-00033-9v5 | 2026-10-11 00:48:21 UTC | [verified](https://github.com/neilmac91/EarningsNerd/pull/1211#issuecomment-6103914456) |
| C2 [1212](https://github.com/neilmac91/EarningsNerd/pull/1212) | 48deb262b266188b90f68f715275e844573b205f | d8c5a2381a1ab3e4bbbb166fcd69311db0c13f3b / 1cb348d5dcd38c9703d0cfb8bf1e7dd96b56e4fa | [38100149646](https://github.com/neilmac91/EarningsNerd/actions/runs/38100149646) | applied=0 skipped=43 | earningsnerd-backend-00481-wqv / earningsnerd-task-worker-00034-v2s | 2026-10-11 01:10:57 UTC | [verified](https://github.com/neilmac91/EarningsNerd/pull/1212#issuecomment-6104082725) |
| F3 [1214](https://github.com/neilmac91/EarningsNerd/pull/1214) | 1426595698cd14cd671f4e142f3b1f3eb64fcbc6 | 517c901a25de6e6d1a137740252fc86a444dd230 / 2843f395fde45906fcbc4fefbfd93237e68f814b | [38101089234](https://github.com/neilmac91/EarningsNerd/actions/runs/38101089234) | applied=0 skipped=43 | earningsnerd-backend-00482-42m / earningsnerd-task-worker-00035-pnt | 2026-10-11 01:28:23 UTC | [verified](https://github.com/neilmac91/EarningsNerd/pull/1214#issuecomment-6104202922) |
| X3 [1215](https://github.com/neilmac91/EarningsNerd/pull/1215) | e85104391ec82a47763385bd3526b1661ab9b292 | 64f0b84488c83699a3980ef446e4350946b9334d / c78b83fca40518897e1c1a37321323b150fc96a1 | [38102021489](https://github.com/neilmac91/EarningsNerd/actions/runs/38102021489) | applied=0 skipped=43 | earningsnerd-backend-00483-rzb / earningsnerd-task-worker-00036-nvs | 2026-10-11 01:45:24 UTC | [verified](https://github.com/neilmac91/EarningsNerd/pull/1215#issuecomment-6104338974) |
| C3 [1216](https://github.com/neilmac91/EarningsNerd/pull/1216) | e61218e4342596c6ec7ccf157397e0317d235de5 | 82cd322e959d0951954d23474f300063384ab570 / 2fbab08d9832b6179c691c3f7023b09becf1bb7c | [38103145575](https://github.com/neilmac91/EarningsNerd/actions/runs/38103145575) | applied=0 skipped=43 | earningsnerd-backend-00484-x6j / earningsnerd-task-worker-00037-csb | 2026-10-11 02:05:22 UTC | [verified](https://github.com/neilmac91/EarningsNerd/pull/1216#issuecomment-6104459940) |
| F4 [1217](https://github.com/neilmac91/EarningsNerd/pull/1217) | 0b5708de028d592781621327dc4b0c3a7274f00b | 3038ccf694affe7343720bb51ee75f6631dbdb9a / c3f7253249563207edf4d6c5336a4f99c8a6eb9d | [38104041389](https://github.com/neilmac91/EarningsNerd/actions/runs/38104041389) | applied=0 skipped=43 | earningsnerd-backend-00485-6tc / earningsnerd-task-worker-00038-m6g | 2026-10-11 02:22:11 UTC | [verified](https://github.com/neilmac91/EarningsNerd/pull/1217#issuecomment-6104577594) |
| X4 [1218](https://github.com/neilmac91/EarningsNerd/pull/1218) | bbc7c89298a49cad3cf0b2f35d310865c0545ea0 | 44107449957d1083601b80d729e6b7aed3198fd6 / 88bece328e7f006760a70229f917730d4ae5e3c4 | [38104998916](https://github.com/neilmac91/EarningsNerd/actions/runs/38104998916) | applied=0 skipped=43 | earningsnerd-backend-00486-vx8 / earningsnerd-task-worker-00039-h4k | 2026-10-11 02:36:24 UTC | [verified](https://github.com/neilmac91/EarningsNerd/pull/1218#issuecomment-6104676056) |
| X5 [1219](https://github.com/neilmac91/EarningsNerd/pull/1219) | abc3fe84d9f9d11871e67072cad4ab9adfb850aa | 777ba27653c443d8f756553dd39bdc8950b694c6 / 860a07be6af9953c63d9c617ad06cae01cbaebfa | [38106052520](https://github.com/neilmac91/EarningsNerd/actions/runs/38106052520) | applied=0 skipped=43 | earningsnerd-backend-00487-bs5 / earningsnerd-task-worker-00040-j9q | 2026-10-11 02:56:25 UTC | [verified](https://github.com/neilmac91/EarningsNerd/pull/1219#issuecomment-6104812438) |

The linked receipts retain independent health, traffic and scheduled-job checks.
From T4 through X5 these are eight jobs, API/worker at 100%, migrations 0/43 and
healthy SEC/database checks. The earlier 41 → 43 migration change came from separate
PR 1191. Verified limiter prerequisite PR 1213 skipped paid evaluations and mutating deploy steps.

## All retained free balance readings

| UTC | USD | Run | Context |
|---|---|---|---|
| 2026-10-09 12:49 | 28.38 | [37932600962](https://github.com/neilmac91/EarningsNerd/actions/runs/37932600962) | Wave 0 ready transitions |
| 2026-10-09 17:23 | 26.76 | [37965926460](https://github.com/neilmac91/EarningsNerd/actions/runs/37965926460) | Review-fix pushes |
| 2026-10-09 17:47 | 26.37 | [37968774003](https://github.com/neilmac91/EarningsNerd/actions/runs/37968774003) | Review-fix pushes |
| 2026-10-09 17:59 | 26.33 | [37970113249](https://github.com/neilmac91/EarningsNerd/actions/runs/37970113249) | #1156 review-fix push |
| 2026-10-09 18:28 | 25.87 | [37973467465](https://github.com/neilmac91/EarningsNerd/actions/runs/37973467465) | #1156 pre-push check |
| 2026-10-09 18:36 | 25.80 | [37974469687](https://github.com/neilmac91/EarningsNerd/actions/runs/37974469687) | #1156 immediately before push |
| 2026-10-09 18:53 | 25.46 | [37976355177](https://github.com/neilmac91/EarningsNerd/actions/runs/37976355177) | #1156 review-fix push |
| 2026-10-09 18:59 | 25.43 | [37977060651](https://github.com/neilmac91/EarningsNerd/actions/runs/37977060651) | #1156 pre-push check |
| 2026-10-09 19:07 | 25.43 | [37978030671](https://github.com/neilmac91/EarningsNerd/actions/runs/37978030671) | #1156 immediately before push |
| 2026-10-10 12:10 | 21.83 | [38050979625](https://github.com/neilmac91/EarningsNerd/actions/runs/38050979625) | Pre-cleanup status check; no inference |
| 2026-10-10 14:07 | 21.83 | [38058342515](https://github.com/neilmac91/EarningsNerd/actions/runs/38058342515) | Before Wave 1 Dead; USD 0.73 summary plus USD 0.06 Copilot reservations fit above the USD 5 floor |
| 2026-10-10 14:12 | 21.83 | [38058680843](https://github.com/neilmac91/EarningsNerd/actions/runs/38058680843) | before ready |
| 2026-10-10 14:24 | 21.65 | [38059463931](https://github.com/neilmac91/EarningsNerd/actions/runs/38059463931) | after eval |
| 2026-10-10 14:43:14 | 21.65 | [38060726184](https://github.com/neilmac91/EarningsNerd/actions/runs/38060726184) | before publication |
| 2026-10-10 14:46:11 | 21.65 | [38060925007](https://github.com/neilmac91/EarningsNerd/actions/runs/38060925007) | before ready |
| 2026-10-10 14:57:38 | 21.47 | [38061673734](https://github.com/neilmac91/EarningsNerd/actions/runs/38061673734) | after eval |
| 2026-10-10 15:30:42 | 21.47 | [38063899001](https://github.com/neilmac91/EarningsNerd/actions/runs/38063899001) | before publication |
| 2026-10-10 15:38:05 | 21.47 | [38064395060](https://github.com/neilmac91/EarningsNerd/actions/runs/38064395060) | before ready |
| 2026-10-10 15:49:56 | 21.29 | [38065188770](https://github.com/neilmac91/EarningsNerd/actions/runs/38065188770) | after eval |
| 2026-10-10 16:49:55 | 21.10 | [38069233314](https://github.com/neilmac91/EarningsNerd/actions/runs/38069233314) | before publication |
| 2026-10-10T16:58:12+00:00 | 21.10 | [38069803376](https://github.com/neilmac91/EarningsNerd/actions/runs/38069803376) | before ready |
| 2026-10-10 17:08:43 | 20.94 | [38070529038](https://github.com/neilmac91/EarningsNerd/actions/runs/38070529038) | after eval |
| 2026-10-10 17:32:35 | 20.91 | [38072161618](https://github.com/neilmac91/EarningsNerd/actions/runs/38072161618) | before publication |
| 2026-10-10 17:38:23 | 20.91 | [38072550136](https://github.com/neilmac91/EarningsNerd/actions/runs/38072550136) | before ready |
| 2026-10-10 17:49:15 | 20.75 | [38073286187](https://github.com/neilmac91/EarningsNerd/actions/runs/38073286187) | after eval |
| 2026-10-10 18:58:49 | 20.73 | [38077947832](https://github.com/neilmac91/EarningsNerd/actions/runs/38077947832) | before publication |
| 2026-10-10T19:04:47+00:00 | 20.73 | [38078355983](https://github.com/neilmac91/EarningsNerd/actions/runs/38078355983) | before ready |
| 2026-10-10T19:15:10+00:00 | 20.56 | [38079047073](https://github.com/neilmac91/EarningsNerd/actions/runs/38079047073) | after eval |
| 2026-10-10 19:39:38 | 20.54 | [38080668615](https://github.com/neilmac91/EarningsNerd/actions/runs/38080668615) | before publication |
| 2026-10-10T19:42:26+00:00 | 20.54 | [38080858173](https://github.com/neilmac91/EarningsNerd/actions/runs/38080858173) | before ready |
| 2026-10-10T19:53:20+00:00 | 20.38 | [38081568971](https://github.com/neilmac91/EarningsNerd/actions/runs/38081568971) | after eval |
| 2026-10-10 20:33:02 | 20.36 | [38084179199](https://github.com/neilmac91/EarningsNerd/actions/runs/38084179199) | before publication |
| 2026-10-10 20:40:22 | 20.36 | [38084650541](https://github.com/neilmac91/EarningsNerd/actions/runs/38084650541) | before ready |
| 2026-10-10 20:50:46 | 20.21 | [38085328933](https://github.com/neilmac91/EarningsNerd/actions/runs/38085328933) | after eval |
| 2026-10-10 21:06:57 | 20.18 | [38086370970](https://github.com/neilmac91/EarningsNerd/actions/runs/38086370970) | before publication |
| 2026-10-10 21:09:37 | 20.18 | [38086540153](https://github.com/neilmac91/EarningsNerd/actions/runs/38086540153) | before ready |
| 2026-10-10 21:20:04 | 20.03 | [38087206045](https://github.com/neilmac91/EarningsNerd/actions/runs/38087206045) | after eval |
| 2026-10-10 21:53:00 | 19.99 | [38089310356](https://github.com/neilmac91/EarningsNerd/actions/runs/38089310356) | before publication |
| 2026-10-10 21:56:49 | 19.99 | [38089547235](https://github.com/neilmac91/EarningsNerd/actions/runs/38089547235) | before ready |
| 2026-10-10 22:08:00 | 19.84 | [38090254771](https://github.com/neilmac91/EarningsNerd/actions/runs/38090254771) | after eval |
| 2026-10-10T22:40:08.7234451Z | 19.81 | [38092274242](https://github.com/neilmac91/EarningsNerd/actions/runs/38092274242) | Recovered run ID for earlier T4 preparation; replaces formerly unbound reading |
| 2026-10-10T23:06:12.4358405Z | 19.81 | [38093841508](https://github.com/neilmac91/EarningsNerd/actions/runs/38093841508) | earlier T4 preparation reading |
| 2026-10-10 23:23 | 19.81 | [38094853081](https://github.com/neilmac91/EarningsNerd/actions/runs/38094853081) | before publication |
| 2026-10-10T23:35:49.6879044Z | 19.63 | [38095574301](https://github.com/neilmac91/EarningsNerd/actions/runs/38095574301) | after retained T4 evals |
| 2026-10-10T23:42:42.7298403Z | 19.63 | [38095960398](https://github.com/neilmac91/EarningsNerd/actions/runs/38095960398) | F2 pre-publication reservation |
| 2026-10-10T23:54:53.5956849Z | 19.48 | [38096639856](https://github.com/neilmac91/EarningsNerd/actions/runs/38096639856) | after retained F2 evals, before merge |
| 2026-10-11T00:06:45.0995216Z | 19.44 | [38097306356](https://github.com/neilmac91/EarningsNerd/actions/runs/38097306356) | retained free reading |
| 2026-10-11T00:19:31.7174943Z | 19.27 | [38098032700](https://github.com/neilmac91/EarningsNerd/actions/runs/38098032700) | retained free reading |
| 2026-10-11T00:21:39.6997844Z | 19.26 | [38098153983](https://github.com/neilmac91/EarningsNerd/actions/runs/38098153983) | C2 first publication: pre-publication |
| 2026-10-11T00:24:39.2372588Z | 19.26 | [38098323071](https://github.com/neilmac91/EarningsNerd/actions/runs/38098323071) | C2 first publication: pre-ready |
| 2026-10-11T00:40:37.2880186Z | 19.07 | [38099230885](https://github.com/neilmac91/EarningsNerd/actions/runs/38099230885) | C2 |
| 2026-10-11T00:53:46.1684531Z | 19.07 | [38099967250](https://github.com/neilmac91/EarningsNerd/actions/runs/38099967250) | F3 |
| 2026-10-11T00:58:29.3792984Z | 19.07 | [38100230045](https://github.com/neilmac91/EarningsNerd/actions/runs/38100230045) | F3 |
| 2026-10-11T01:09:38.4655535Z | 18.90 | [38100876233](https://github.com/neilmac91/EarningsNerd/actions/runs/38100876233) | retained free reading |
| 2026-10-11T01:11:24.2438009Z | 18.89 | [38100983822](https://github.com/neilmac91/EarningsNerd/actions/runs/38100983822) | retained free reading |
| 2026-10-11T01:14:56.2391351Z | 18.89 | [38101184547](https://github.com/neilmac91/EarningsNerd/actions/runs/38101184547) | retained free reading |
| 2026-10-11T01:26:05.9425388Z | 18.73 | [38101816564](https://github.com/neilmac91/EarningsNerd/actions/runs/38101816564) | retained free reading |
| 2026-10-11T01:27:38.3908560Z | 18.70 | [38101901520](https://github.com/neilmac91/EarningsNerd/actions/runs/38101901520) | retained free reading |
| 2026-10-11T01:32:10.9530068Z | 18.70 | [38102157016](https://github.com/neilmac91/EarningsNerd/actions/runs/38102157016) | retained free reading |
| 2026-10-11T01:42:47.4847761Z | 18.55 | [38102741925](https://github.com/neilmac91/EarningsNerd/actions/runs/38102741925) | retained free reading |
| 2026-10-11T01:49:45.5210966Z | 18.52 | [38103130549](https://github.com/neilmac91/EarningsNerd/actions/runs/38103130549) | F4 prepublication |
| 2026-10-11T01:50:51.1643386Z | 18.52 | [38103195436](https://github.com/neilmac91/EarningsNerd/actions/runs/38103195436) | F4 pre-ready |
| 2026-10-11T01:58:49.1464895Z | 18.43 | [38103627087](https://github.com/neilmac91/EarningsNerd/actions/runs/38103627087) | F4 INTERIM during evaluation; not post-eval |
| 2026-10-11T02:01:49.2908915Z | 18.37 | [38103800791](https://github.com/neilmac91/EarningsNerd/actions/runs/38103800791) | F4 actual post-eval |
| 2026-10-11T02:05:41.7823827Z | 18.34 | [38104017352](https://github.com/neilmac91/EarningsNerd/actions/runs/38104017352) | X4 prepublication |
| 2026-10-11T02:07:13.6585173Z | 18.34 | [38104101679](https://github.com/neilmac91/EarningsNerd/actions/runs/38104101679) | X4 pre-ready |
| 2026-10-11T02:18:26.1316694Z | 18.17 | [38104715888](https://github.com/neilmac91/EarningsNerd/actions/runs/38104715888) | X4 actual post-eval |
| 2026-10-11T02:22:41.3591018Z | 18.15 | [38104949332](https://github.com/neilmac91/EarningsNerd/actions/runs/38104949332) | X5 prepublication |
| 2026-10-11T02:24:47.3149724Z | 18.15 | [38105061976](https://github.com/neilmac91/EarningsNerd/actions/runs/38105061976) | X5 pre-ready |
| 2026-10-11T02:35:50.3160717Z | 17.98 | [38105662807](https://github.com/neilmac91/EarningsNerd/actions/runs/38105662807) | X5 actual post-eval |
| 2026-10-11T02:47:28.4876132Z | 17.97 | [38106280469](https://github.com/neilmac91/EarningsNerd/actions/runs/38106280469) | Closeout free reading; no new reservation |

All five formerly missing UTCs are filled at their original precision. The former
unbound USD 19.81 reading at 2026-10-10T22:40:08.7234451Z is run 38092274242, included
once. F4's during-summary USD 18.43 and actual post-eval USD 18.37 readings are distinct.

## Measured targets and gate provenance

| Facade | Original estimate | Final actual | Decision |
|---|---|---|---|
| Copilot M1 | ≈800 | 619 | Within estimate |
| Facts M2 | ≤60 | 60 | Met |
| Trend M3 | ≤60 | 204 | Exceeded; compatibility imports/exports retained in [T3](https://github.com/neilmac91/EarningsNerd/pull/1205) |
| OpenAI M4 | ≈670–840 | 574 | Below estimate band |
| XBRL M5 | ≤300 | 348 | Exceeded deliberately; intact async class/method and mandatory compatibility surface |
| Instance M6 | ≈45 | 71 | Exceeded; complete compatibility contract retained in [I1](https://github.com/neilmac91/EarningsNerd/pull/1187) |

The original estimates remain as history beside these measured results; not all
numeric targets were met. Ratchet's actual-size row governs. Final inventory: 55 rows,
comprising six facades and 49 family modules; 53 nonempty files have actual ceilings,
and two empty initializers use the schema minimum of 1. All 49 former default
600-line ceilings are explicit. Existing 100-line file slack and 20-line function
slack remain, along with default file/function ceilings of 600/80 and six frozen
unsplit rows: `_resolve_citations`: 114, `reconcile_facts`: 109, `upsert_facts_bulk`: 84,
`remediate_industry_facts`: 102, `_assemble_structured_summary`: 87, `get_xbrl_data`: 81.
No ceiling raises or new exceptions. Ratchet's existing gate had exactly one
committed file-budget mutation (prompt ceiling 284 → 283), rejected and restored;
47 focused tests passed. [Ratchet #1220](https://github.com/neilmac91/EarningsNerd/pull/1220) binds this final inventory.
I2 reader repoints are included in X4; X5 was taken. No orchestration or formatting
change is justified solely to meet the original estimate.


| Stage | Final candidate / published head | Actual gate execution head | Entire tested tree | Original full-gate tail |
|---|---|---|---|---|
| F4 | 0b5708de028d592781621327dc4b0c3a7274f00b | 30740eccae7ebefbd37c23360a52d3d61ab5b242 | c3f7253249563207edf4d6c5336a4f99c8a6eb9d | ========== 6737 passed, 39 skipped, 153 warnings in 82.89s (0:01:22) =========== |
| X4 | bbc7c89298a49cad3cf0b2f35d310865c0545ea0 | 28d2201b06e7f0b6c07ca2962c46f8a7d7692d0b | 88bece328e7f006760a70229f917730d4ae5e3c4 | ========== 6737 passed, 39 skipped, 153 warnings in 79.01s (0:01:19) =========== |
| X5 | abc3fe84d9f9d11871e67072cad4ab9adfb850aa | a816b5b1bca652d5e0dac933d69d51cedead344f | 860a07be6af9953c63d9c617ad06cae01cbaebfa | ========== 6737 passed, 39 skipped, 153 warnings in 84.83s (0:01:24) =========== |
| Ratchet | f1152041eccc81ff94751387b661649fe916758b | 75355b44fa90edd5e321d3a9b6f24f099c7b255b | a7415b8e73484df28aec91622e724a77a4d95489 | ========== 6737 passed, 39 skipped, 153 warnings in 81.59s (0:01:21) =========== |

| Earlier tail stage | Actual gate execution head | Entire tested tree | Original tail |
|---|---|---|---|
| f3 | 56a241426cb92e984163ac2b07c9a320a073b368 | 2843f395fde45906fcbc4fefbfd93237e68f814b | ========== 6737 passed, 39 skipped, 153 warnings in 85.25s (0:01:25) =========== |
| x3 | 359a564668ac3eaa277de25c2e704e8cdc84cb17 | c78b83fca40518897e1c1a37321323b150fc96a1 | ========== 6737 passed, 39 skipped, 153 warnings in 82.05s (0:01:22) =========== |
| c3 | 62fe44da1bcafc01a4a033ba438b87935850d149 | 2fbab08d9832b6179c691c3f7023b09becf1bb7c | ========== 6737 passed, 39 skipped, 153 warnings in 81.99s (0:01:21) =========== |

## Remaining work and records verification

All final-stage receipt requirements are filled.

The records PR carries its exact candidate identity, local link/anchor verification,
existing agent-workflow gate and review. Its post-merge receipt comment records the
actual PR/main CI and paid/deployment step dispositions.
Keep separate Rule 7 timestamp and Wave 0 behavior follow-ups (missing-identifier
NaN, numeric model filing_date, model-supplied structured-output keys), and the
existing Founder OUTPUT REFERENCE prompt-byte decision until separately resolved.
This closeout changes three task documents. Original red verdicts and unknown
costs remain visible; the separate behavior follow-ups and the founder decision, open at closeout, are resolved below.


### Follow-ups resolved — 2026-10-11

Rule 7 timestamps and the three Wave 0 behavior fixes landed in #1222, #1224, #1227 and #1231;
[deployment and evaluation receipts](https://github.com/neilmac91/EarningsNerd/pull/1231#issuecomment-6108047072).
The founder subsequently authorized removing the unused OUTPUT REFERENCE plumbing while retaining
all request bytes and existing snapshots. That cleanup closes the remaining decision from this
refactor: no prompt instructions, model settings, production flags or baseline scores change.
The earlier statement that deletion necessarily changes prompt bytes was too broad; activating
prompt splitting would change them, but deleting the empty reference slot's machinery need not.

The plan's last two follow-ups closed in #1245 (merged as `834f44b5`; [deploy receipt](https://github.com/neilmac91/EarningsNerd/pull/1245#issuecomment-6111392692)):
three comments now match their code, the always-None summary writer fields and the trend catalogue's unreachable
duplicate-id guard are removed, and the facts identity dedup stays as protection with an executed counterexample.
#1243 (merged as `85439925` on 2026-10-13, tests only) closed the move proof's open findings from #1177's re-probe
and #1190's "Not in this PR", and the findings its own reviews raised: two routine-tier lenses, eleven Codex rounds
and an AI-assisted review. Three of those findings were defects the PR itself had introduced and then fixed: a
class-body `COUNT += 1` (a false OK from `d5cff540`), a class's own global stores (a false OK), and a lambda in a
postponed annotation (a false FAIL). Codex reviewed `13e2f22d` with no findings. The merged head `b8128f4b` only
merged main in, for #1261's gitleaks fingerprints, and passed `review-gate` on a review override recorded in the
body and authorized in the PR's session; the override line's quota claim is corrected on the PR
([comment](https://github.com/neilmac91/EarningsNerd/pull/1243#issuecomment-6156455978)). Its body keeps the proof's retained boundaries with the evidence that merged moves
stayed within them: known false OKs (a same-name import retarget, and a class body's namespace written by a
function it calls or reached under another spelling), cross-file import order, and the reach's fail-closed rules,
`__set_name__` among them. The open threads on #1177, #1190 and #1243 keep the founder's call on those
boundaries.

### Follow-up spend (outside the programme ceiling)

The programme ledger above is unchanged: USD 3.815166 known plus the USD 0.553850 retained hold. Follow-up work
after the closeout is accounted separately, once each:

| Work | PRs | Known USD | Source |
|---|---|---|---|
| Rule 7 and Wave 0 behavior fixes | #1222, #1224, #1227, #1231 | 1.087982 (ceiling 3.16; no hold) | [receipt](https://github.com/neilmac91/EarningsNerd/pull/1231#issuecomment-6108047072) |
| Acceptance-runner process groups | #1236 | 0.529476 over three `eval-baseline` jobs (0.177600, 0.172858 cancelled, 0.179018), plus two calls of unknown cost | jobs [114474633624](https://github.com/neilmac91/EarningsNerd/actions/runs/38140985171/job/114474633624), [114480247305](https://github.com/neilmac91/EarningsNerd/actions/runs/38142908321/job/114480247305), [114482117274](https://github.com/neilmac91/EarningsNerd/actions/runs/38143526271/job/114482117274) |
| OUTPUT REFERENCE cleanup | #1237 | 0.183869 (summary 0.177336, Copilot 0.006533) | [#1237](https://github.com/neilmac91/EarningsNerd/pull/1237) |
| Follow-ups 5 and 6 | #1245 | 0.183647 (summary 0.177031, Copilot 0.006616) | [#1245](https://github.com/neilmac91/EarningsNerd/pull/1245) |
| Move-proof hardening | #1243 | 0 (tests only; no paid path) | [#1243](https://github.com/neilmac91/EarningsNerd/pull/1243) |

Each figure is quoted from the receipt or job log its row links, where it sums the calls' logged
`estimated_cost_usd` (`app/services/llm_pricing.py`); a report's `total_cost_usd: 0.0` and wallet movement are not
cost evidence. #1236's body gave about USD 0.18 per run. Its
second job was cancelled when a new head superseded it, after 68 of its 70 attempts had logged usage. The last
filing's two attempts were in flight at the cancellation (13:31:50Z) and logged none, so their cost is unknown.

### The retained T4 hold

USD 0.553850 stays held. T4's summary run [38094895509](https://github.com/neilmac91/EarningsNerd/actions/runs/38094895509) logged 71 summary calls. One,
the AMZN 10-K attempt (accession 0001018724-26-000004) at 2026-10-10T23:27:52.389Z, failed after 119 ms with a null
model, null usage and no cost; its retry at 23:28:05.502Z succeeded at an estimated USD 0.002544. No per-call
provider billing record is available, so the failed call's cost cannot be established, and the hold is not
released. The run's artifact expires around 2026-10-24; these facts are kept here.

### Free balance readings for the follow-up work

| UTC | USD | Run | Context |
|---|---|---|---|
| 2026-10-11T12:20:28Z | 16.28 | [38138881169](https://github.com/neilmac91/EarningsNerd/actions/runs/38138881169) | #1236 before its evaluations |
| 2026-10-11T13:00:10.5280611Z | 16.22 | [38141422979](https://github.com/neilmac91/EarningsNerd/actions/runs/38141422979) | #1237 before its evaluations |
| 2026-10-11T13:17:24.1926996Z | 15.95 | [38142576335](https://github.com/neilmac91/EarningsNerd/actions/runs/38142576335) | #1237 after its evaluations |
| 2026-10-11T14:03:07Z | 15.51 | [38145608559](https://github.com/neilmac91/EarningsNerd/actions/runs/38145608559) | after #1236's merge |
| 2026-10-11T15:18:36.1493744Z | 14.88 | [38150729044](https://github.com/neilmac91/EarningsNerd/actions/runs/38150729044) | another session's reading |
| 2026-10-11T15:58:14.0654598Z | 14.88 | [38153485740](https://github.com/neilmac91/EarningsNerd/actions/runs/38153485740) | before #1245's draft (USD 0.79 reserved) |
| 2026-10-11T16:27:17.6408655Z | 14.70 | [38155520396](https://github.com/neilmac91/EarningsNerd/actions/runs/38155520396) | after #1245's summary evaluation, before ready |
| 2026-10-11T17:09:31.9954083Z | 14.69 | [38158460366](https://github.com/neilmac91/EarningsNerd/actions/runs/38158460366) | after #1245's evaluations and merge |

The Wave 0 fixes' readings are in [#1231's receipt](https://github.com/neilmac91/EarningsNerd/pull/1231#issuecomment-6108047072). The readout's other
runs since the closeout were taken for other work.
