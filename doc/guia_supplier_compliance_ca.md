# Guia de supplier_compliance

Documentació funcional sobre les fitxes tècniques i l’homologació de productes i proveïdors. Aquest document s’anirà ampliant amb les explicacions següents.

## 1. Tipus d’abast («Tipos de alcance»)

El tipus d’abast indica **què estàs homologant** dins del mòdul.

| Exemple d’abast | Què representa |
|---|---|
| Matèria primera | Una farina o un ingredient d’un proveïdor. |
| Envàs | Una bossa o una caixa destinada al producte. |
| Servei | Un servei prestat per un proveïdor. |

### Per a què serveix

1. **Classificar les homologacions**, per distingir els diferents àmbits.
2. **Determinar si és obligatori indicar un producte.** Cada tipus té l’opció «Producte obligatori». Si està marcada, el sistema no deixa guardar una homologació sense producte intern.
3. **Seleccionar la plantilla d’homologació aplicable**, juntament amb l’empresa i la categoria del producte. La plantilla permet carregar els requisits i controls corresponents. La selecció automàtica necessita empresa, tipus d’abast i producte intern.

### Exemple pràctic

Pots configurar que les **matèries primeres** requereixin un producte i utilitzin una plantilla amb el requisit de fitxa tècnica i controls alimentaris. Per als **envasos**, pots configurar una plantilla amb documentació de contacte alimentari i assajos de migració.

Aquests són exemples de configuració: el nom de l’abast, per si sol, no imposa aquesta documentació. Cal definir els requisits i controls a la plantilla corresponent. La plantilla crea les línies de control; la documentació de cada proveïdor s’ha de completar a la fitxa.

### Diferència respecte d’una certificació

El tipus d’abast identifica l’àmbit de l’homologació. Un esquema de certificació, com IFS o BRC, identifica la certificació que es registra. Són conceptes diferents dins del mòdul.

### Camps de configuració

- **Nom:** nom visible del tipus d’abast.
- **Codi:** identificador curt, útil en importacions i filtres.
- **Producte obligatori:** exigeix vincular la fitxa a un producte intern.
- **Descripció:** explicació interna de quan s’ha d’utilitzar aquest abast.

Referència de la implementació: `tryton/trytond/trytond/modules/supplier_compliance/compliance.py`.

## 2. Tipus de requisit («Tipos de requisito»)

El tipus de requisit defineix **quina documentació o informació demanes per a una homologació**. És un catàleg reutilitzable: es defineix una vegada i es pot utilitzar en les fitxes de diferents productes i proveïdors.

| Exemple de tipus de requisit | Què es demana | Classe orientativa |
|---|---|---|
| Fitxa tècnica | El document amb les característiques del producte. | Document |
| Declaració d’al·lèrgens | La declaració del proveïdor sobre els al·lèrgens. | Declaració |
| Declaració de no OGM | La declaració sobre organismes modificats genèticament. | Declaració |
| Qüestionari del proveïdor | El qüestionari emplenat pel proveïdor. | Document |

Són exemples de configuració, no una llista de requisits obligatoris per a tots els proveïdors.

### Per a què serveix

1. **Unificar què es demana.** Permet utilitzar el mateix tipus «Fitxa tècnica» en moltes homologacions.
2. **Definir els requisits de les plantilles.** Una plantilla pot incloure diversos tipus de requisit. Quan s’aplica a una fitxa, afegeix les línies que falten amb l’estat «Falta», sense duplicar els tipus que ja hi són.
3. **Fer el seguiment de cada requisit a cada fitxa.** La línia concreta permet registrar l’estat, les versions, les dates i el valor o referència del document. Els fitxers s’adjunten a les versions.
4. **Establir l’antelació per demanar una actualització.** Els dies d’avís del tipus s’utilitzen, juntament amb la data de caducitat del document, per calcular l’indicador «Sol·licitar actualització».

### Camps de configuració

- **Nom:** nom visible del requisit, per exemple «Fitxa tècnica».
- **Codi:** identificador curt, per exemple `FT`.
- **Classe:** Document, Declaració, Anàlisi, Certificat o Altres. Classifica el requisit; escollir Anàlisi o Certificat no crea automàticament una analítica o un certificat a les altres pestanyes.
- **Requereix document:** indica que s’espera un fitxer adjunt.
- **Controla la caducitat:** indica que el requisit pot caducar.
- **Dies d’avís de caducitat:** antelació amb què el document apareix com a pendent de demanar una actualització.
- **Descripció:** instruccions internes sobre què es demana i quan s’aplica.

### Exemple pràctic

Crees el tipus **«Qüestionari del proveïdor»**, de classe Document, marques que requereix document i que controla la caducitat, i hi poses **30 dies d’avís**. Després l’inclous a la plantilla corresponent.

Quan aquesta plantilla s’aplica a una homologació, s’hi afegeix el requisit amb l’estat «Falta». Quan reps el qüestionari, pots registrar-ne una versió, adjuntar el PDF, informar les dates i establir l’estat que correspongui després de revisar-lo.

Si informes una data de caducitat, l’indicador «Sol·licitar actualització» es marca quan falten 30 dies o menys, inclòs el dia de caducitat. Un cop passada aquesta data, es marca l’indicador «Caducat» i deixa de marcar-se el de sol·licitar actualització. Si no hi ha data de caducitat o els dies d’avís són zero, no es marca l’indicador de sol·licitar actualització.

### Comportament actual de les opcions

En la implementació revisada, **«Requereix document» i «Controla la caducitat» són indicacions de configuració**: no obliguen automàticament a adjuntar un fitxer ni a informar una data. El càlcul dels indicadors de caducitat utilitza la data informada i els dies d’avís, sense dependre d’aquestes dues caselles.

Els dies d’avís calculen un indicador de seguiment; no envien per si sols cap correu. Els indicadors de caducitat tampoc canvien automàticament l’estat del requisit ni el de l’homologació.

### Relació amb el tipus d’abast

En una homologació de farina, el **tipus d’abast** pot ser «Matèria primera» i els **tipus de requisit** poden ser «Fitxa tècnica», «Declaració d’al·lèrgens» i «Declaració de no OGM». La plantilla agrupa els requisits que vols demanar per a aquell abast i, si escau, categoria de producte.

Referència de la implementació: `tryton/trytond/trytond/modules/supplier_compliance/compliance.py`, models `RequirementType`, `ComplianceTemplateRequirement`, `Requirement` i `RequirementVersion`.

## 3. Esquemes de certificació («Esquemas de certificación»)

L’esquema de certificació identifica **a quina certificació correspon un certificat** registrat a la fitxa d’homologació. És un catàleg reutilitzable: pots definir, per exemple, un esquema «IFS» i utilitzar-lo en els certificats de diferents fitxes.

L’esquema conté la configuració comuna. El número del certificat, l’entitat emissora, les dates i el PDF corresponen al certificat concret i a les seves versions.

### Per a què serveix

1. **Classificar els certificats.** Permet identificar l’esquema de cadascun, per exemple IFS, FSC o GRS.
2. **Incloure certificacions en les plantilles d’homologació.** En aplicar una plantilla, es creen les línies de certificat dels esquemes que falten. Es conserven les línies existents.
3. **Configurar l’antelació per demanar una renovació.** Els dies d’avís de l’esquema s’utilitzen amb la data de caducitat de cada certificat per calcular l’indicador «Sol·licitar actualització».
4. **Organitzar l’historial de renovacions.** Dins de cada fitxa hi ha un certificat per esquema; les renovacions es registren com a versions d’aquest certificat.

### Camps de configuració

- **Nom:** nom visible de l’esquema, per exemple «IFS».
- **Codi:** identificador curt de l’esquema.
- **Dies d’avís de caducitat:** dies d’antelació per indicar que cal demanar la renovació, per exemple 45.
- **Descripció:** notes internes sobre quan es demana o en quins casos s’utilitza.

### Dades del certificat concret

A la fitxa d’homologació, la línia de certificat identifica l’esquema. Les versions permeten registrar:

- La versió o revisió i quina és la vigent.
- El número del certificat i l’entitat emissora.
- Les dates d’emissió i de caducitat.
- L’abast declarat al certificat.
- Les notes i els fitxers adjunts, com el PDF rebut.

L’**abast del certificat** és un text que descriu què cobreix aquell document. És un camp diferent del **tipus d’abast de l’homologació**, com «Matèria primera» o «Envàs».

### Exemple pràctic

Crees l’esquema **«IFS»** amb **45 dies d’avís** i l’inclous a la secció de certificats d’una plantilla. Quan la plantilla s’aplica a una fitxa, s’hi afegeix una línia de certificat IFS si encara no existeix.

Quan reps el certificat del proveïdor, hi crees una versió i completes el número, l’emissor, les dates i l’abast declarat, i hi adjuntes el PDF. Crear la línia des de la plantilla no acredita que el proveïdor ja disposi del certificat.

Quan falten 45 dies o menys per caducar, inclòs el dia de caducitat, es marca «Sol·licitar actualització». Després de la data de caducitat, es marca «Caducat» i deixa de marcar-se l’indicador de sol·licitar actualització.

Quan arriba la renovació, utilitzes **«Nova versió»** per conservar l’historial i completar la nova revisió. Aquest botó deixa buides la revisió, les dates i els adjunts de la nova versió; cal completar-los i revisar les dades que s’han conservat.

### Comportament actual

- Sense data de caducitat, o amb zero dies d’avís, no es marca «Sol·licitar actualització».
- Els avisos són indicadors de seguiment; configurar-los no envia per si sol cap correu.
- Els certificats no tenen els estats «Falta», «Pendent» o «Vàlid» dels requisits. Disposen de versions, dates i indicadors de caducitat.
- Un certificat caducat no canvia automàticament l’estat de l’homologació. La revisió i la decisió sobre l’homologació corresponen a l’usuari.
- El sistema comprova que, si s’informen totes dues dates en una versió, la caducitat no sigui anterior a l’emissió.

### Relació amb els conceptes anteriors

| Concepte | Què identifica | Exemple |
|---|---|---|
| Tipus d’abast | Què s’està homologant. | Matèria primera |
| Tipus de requisit | Quina documentació o informació es demana. | Fitxa tècnica |
| Esquema de certificació | A quina certificació correspon el certificat. | IFS |

Classificar un tipus de requisit com a «Certificat» no el vincula automàticament a un esquema ni crea una línia a la pestanya de certificats. Per gestionar número, emissor, abast i renovacions del certificat, s’utilitzen els certificats vinculats a esquemes.

Referència de la implementació: `tryton/trytond/trytond/modules/supplier_compliance/compliance.py`, models `Scheme`, `ComplianceTemplateCertificate`, `Certificate` i `CertificateVersion`.

## 4. Tipus d’al·lèrgens alimentaris («Tipos de alérgenos alimentarios»)

Els tipus d’al·lèrgens alimentaris són el **catàleg d’al·lèrgens que pots seleccionar en les fitxes d’homologació**. Permeten registrar la informació declarada pel proveïdor amb noms comuns i reutilitzables, per exemple «Gluten», «Soja» o «Sèsam».

El catàleg identifica l’al·lergen. La presència, la possible presència o l’absència s’indiquen a la fitxa concreta del producte i proveïdor, dins de l’apartat d’al·lèrgens d’Alimentació.

### Per a què serveixen

1. **Unificar els noms dels al·lèrgens.** El mateix tipus es pot utilitzar en moltes fitxes, sense haver d’escriure el nom lliurement en cada declaració.
2. **Detallar la declaració del proveïdor.** Per a cada al·lergen registrat a la fitxa, s’indica l’estat declarat.
3. **Identificar d’on surt la informació.** Cada línia de la fitxa permet informar la font, la data de declaració i les notes.

### Camps de configuració del tipus

- **Nom:** nom visible de l’al·lergen, per exemple «Gluten».
- **Codi:** identificador intern curt, per exemple `GL`.
- **Actiu:** permet mantenir disponible el tipus o desactivar-lo per a la selecció habitual.
- **Descripció:** explicació interna de l’al·lergen o del criteri amb què s’utilitza.

El tipus no conté dates de caducitat, dies d’avís ni un estat de presència: aquestes dades no formen part del catàleg.

### Dades de cada declaració a la fitxa

- **Al·lergen:** tipus seleccionat del catàleg.
- **Estat:** resultat declarat per a aquell al·lergen.
- **Font:** document o origen de la informació, per exemple «Fitxa tècnica rev. 3». És un camp de text, no un enllaç automàtic a un document.
- **Data de declaració:** data de la informació declarada.
- **Notes:** aclariments o text original del proveïdor.

Els estats disponibles són:

| Estat | Ús en el registre |
|---|---|
| Conté | Registrar que el proveïdor declara la presència de l’al·lergen. |
| Pot contenir | Registrar una possible presència declarada, com ara traces. |
| Contaminació creuada | Registrar la informació declarada sobre contaminació creuada. |
| Absent | Registrar que el proveïdor declara l’absència de l’al·lergen. |
| Desconegut | Indicar que no es disposa d’una declaració clara. És l’estat inicial. |

Aquests estats es trien manualment segons la informació disponible; el mòdul no els dedueix dels ingredients ni analitza el PDF. No tenir una línia d’un al·lergen tampoc equival a declarar-lo absent.

### Exemple pràctic

En una fitxa d’homologació d’una barreja de farines, reps una fitxa tècnica que declara gluten i possible presència de sèsam. Pots registrar:

| Al·lergen | Estat | Font |
|---|---|---|
| Gluten | Conté | Fitxa tècnica rev. 3 |
| Sèsam | Pot contenir | Fitxa tècnica rev. 3 |

Completes la data de declaració i les notes que calguin. Els tipus «Gluten» i «Sèsam» es reutilitzen en altres fitxes, on poden tenir estats diferents segons la declaració de cada proveïdor.

### Relació amb el requisit «Declaració d’al·lèrgens»

El **tipus de requisit «Declaració d’al·lèrgens»** permet demanar i gestionar el document, les seves versions i els adjunts. Els **tipus d’al·lèrgens alimentaris** permeten desglossar la informació d’aquell document en línies consultables a la fitxa.

Per exemple, pots conservar el PDF a la versió del requisit i registrar, a l’apartat d’al·lèrgens, què declara sobre gluten i sèsam. Aquests dos apartats es completen per separat: adjuntar el document no emplena automàticament les línies d’al·lèrgens.

### Comportament actual

- Crear un tipus al catàleg no afegeix automàticament una línia a totes les fitxes.
- Les plantilles d’homologació no generen les línies d’al·lèrgens. Poden incloure el requisit documental, però el detall dels al·lèrgens es registra a la fitxa.
- Les declaracions d’al·lèrgens no tenen versions pròpies ni el botó «Nova versió». Per conservar les revisions del document font, es poden utilitzar les versions del requisit corresponent.
- No hi ha data de caducitat ni avisos de renovació propis de la línia d’al·lergen. La data de declaració serveix per identificar la informació registrada.
- L’estat d’un al·lergen no canvia automàticament l’estat de l’homologació.

Referència de la implementació: `tryton/trytond/trytond/modules/supplier_compliance/food.py`, models `FoodAllergenType` i `FoodAllergen`; relació `food_allergens` i aplicació de plantilles a `compliance.py`.

## 5. Famílies d’envasos («Familias de envases»)

Les famílies d’envasos serveixen per **agrupar diverses referències d’envasos d’un mateix proveïdor** que tenen característiques comunes. Per exemple, pots agrupar diferents mides de bosses de paper dins de la família «Bosses de paper».

Cada família pertany a una empresa i a un proveïdor. Cada fitxa d’homologació pot tenir una família d’envasos assignada, de manera opcional.

### Per a què serveixen

1. **Organitzar les referències relacionades.** Permeten identificar quines fitxes formen part d’un mateix grup d’envasos del proveïdor.
2. **Descriure característiques comunes.** La família permet indicar el material compartit i les observacions generals.
3. **Anotar criteris comuns de documentació.** Per exemple, pots indicar a les notes que diverses referències estan cobertes per una mateixa declaració de conformitat. Aquesta anotació és informativa; la família no distribueix automàticament el document entre les fitxes.

### Camps de configuració

- **Empresa:** empresa a la qual pertany la família. És obligatòria i es proposa l’empresa del context de treball.
- **Proveïdor:** proveïdor dels envasos agrupats. És obligatori.
- **Nom:** nom identificatiu, per exemple «Bosses de paper amb finestra».
- **Codi:** identificador intern, per exemple `BOSSES-FINESTRA`.
- **Material:** descripció general del material compartit, per exemple «Paper + PE».
- **Actiu:** permet mantenir disponible la família o desactivar-la per a la selecció habitual.
- **Notes:** observacions comunes, com una referència a la documentació que cobreix els articles.

En seleccionar la família des d’una fitxa, el sistema filtra les opcions segons el proveïdor i l’empresa informats.

### Exemple pràctic

Un proveïdor et subministra tres bosses de paper amb finestra, amb mides diferents. Crees la família **«Bosses de paper amb finestra»** per a aquell proveïdor i hi indiques el material **«Paper + PE»**.

| Fitxa d’homologació | Família assignada | Dimensions a l’especificació de la fitxa |
|---|---|---|
| Bossa petita | Bosses de paper amb finestra | 20 × 30 cm |
| Bossa mitjana | Bosses de paper amb finestra | 25 × 40 cm |
| Bossa gran | Bosses de paper amb finestra | 30 × 50 cm |

La família agrupa les tres fitxes. Cada fitxa conserva les seves especificacions tècniques, declaracions de conformitat, assajos de migració i estat d’homologació.

Si el proveïdor entrega una declaració que cobreix les tres referències, pots deixar-ho indicat a les notes de la família i registrar la documentació corresponent a les fitxes afectades, comprovant quines referències cobreix el document.

### Diferència respecte de les especificacions de l’envàs

El **material de la família** és una descripció general compartida. Les **especificacions de cada fitxa** detallen el producte concret: tipus d’envàs, materials, dimensions, gramatge, contacte alimentari, condicions d’ús o contingut reciclat.

El material informat a la família no s’emplena ni se sincronitza automàticament amb el material de les especificacions.

### Comportament actual

- Assignar una família és opcional i no substitueix la fitxa individual de cada article.
- La família no té estat d’homologació, versions documentals, caducitats ni avisos propis.
- Assignar-la no copia conformitats, certificats, assajos ni adjunts entre fitxes.
- Canviar les notes o el material de la família no modifica les especificacions ni l’estat de les fitxes associades.
- La família no determina quina plantilla d’homologació s’aplica. La selecció de plantilla utilitza l’empresa, el tipus d’abast i la categoria del producte.

### Relació amb els conceptes anteriors

| Concepte | Exemple en una fitxa de bossa |
|---|---|
| Tipus d’abast | Envàs |
| Família d’envasos | Bosses de paper amb finestra d’un proveïdor concret |
| Tipus de requisit | Fitxa tècnica |
| Especificació de l’envàs | Bossa de paper + PE, dimensions 20 × 30 cm |
| Conformitat de l’envàs | Declaració del proveïdor amb les referències cobertes i les condicions d’ús |

Referència de la implementació: `tryton/trytond/trytond/modules/supplier_compliance/packaging.py`, models `PackagingFamily`, `PackagingSpecification` i `PackagingCompliance`; camp `packaging_family` i selecció de plantilles a `compliance.py`.

## 6. Plantilles d’homologació («Plantillas de homologación»)

Una plantilla d’homologació defineix **quins requisits i controls vols preparar a les fitxes d’un determinat àmbit i categoria de producte**. Permet reutilitzar una estructura de treball sense haver d’afegir totes les línies manualment a cada fitxa.

La plantilla conté els tipus de documents i controls que demanes. Els documents rebuts, les dates, els resultats i les versions de cada proveïdor es completen a la fitxa d’homologació.

### Per a què serveixen

1. **Unificar el contingut inicial de les fitxes.** Els productes que compleixen els criteris de la plantilla reben les línies configurades.
2. **Adaptar els controls al tipus de producte.** Pots tenir una plantilla general per a matèries primeres i una d’específica per a una categoria, com «Farines».
3. **Preparar diversos apartats alhora.** Una mateixa plantilla pot incloure requisits, certificats, analítiques i controls d’envasos.
4. **Reutilitzar una fitxa com a base.** El botó «Crear plantilla» d’una fitxa permet recuperar-ne l’estructura de controls.

### Camps de configuració

- **Empresa:** empresa a la qual pertany la plantilla. És obligatòria.
- **Activa:** només les plantilles actives participen en la selecció automàtica.
- **Nom:** nom descriptiu, per exemple «Homologació de farines».
- **Tipus d’abast:** àmbit al qual s’aplica, per exemple «Matèria primera» o «Envàs». És obligatori.
- **Categoria de producte:** categoria opcional que concreta l’aplicació. Si queda buida, la plantilla és general per a aquella empresa i aquell abast.
- **Notes:** instruccions internes sobre l’ús de la plantilla.

El sistema comprova que no es dupliqui la combinació d’empresa, tipus d’abast i categoria, inclosa la categoria buida.

### Què pots configurar a les línies

| Apartat | Dades de la plantilla | Què es prepara a la fitxa |
|---|---|---|
| Requisits | Tipus de requisit i ordre. | Una línia per tipus, inicialment amb l’estat «Falta». |
| Certificats | Esquema de certificació i ordre. | Una línia per esquema, pendent de completar amb el certificat rebut. |
| Analítiques alimentàries | Nom del tipus d’anàlisi, dies d’avís de revisió i ordre. | Una línia per tipus d’anàlisi amb els dies d’avís configurats. |
| Conformitats d’envasos | Referència opcional, normativa declarada, dies d’avís de caducitat i ordre. | Una línia amb aquestes dades i estat «Pendent». |
| Assajos de migració | Tipus d’assaig, dies d’avís de revisió i ordre. | Una línia per tipus d’assaig amb els dies d’avís configurats. |

Els assajos permeten seleccionar migració global, migració específica, metalls pesants, tintes d’impressió o altres. Els dies d’avís dels requisits i certificats es configuren als seus tipus de requisit i esquemes, respectivament.

### Com es tria la plantilla

**Consulta ràpida:** pots triar una plantilla al camp **«Plantilla d’homologació»** de la fitxa. Aquesta selecció manual té prioritat sobre la categoria del producte. Si deixes el camp buit, el sistema la determina automàticament a partir de l’empresa, el tipus d’abast i les categories del producte intern. Per exemple, si tens una plantilla general de matèries primeres i una altra per a «Farines», un producte d’aquesta categoria utilitzarà la de «Farines» quan no hagis triat cap plantilla manual.

En cada aplicació s’utilitza una sola plantilla, sense sumar l’automàtica i la manual ni la general i l’específica. Sense producte intern no se’n selecciona cap automàticament, però sí que pots triar-ne una manualment. Quan s’aplica, afegeix els controls que falten i conserva els existents: canviar de plantilla, producte o abast no elimina els controls anteriors.

### Selecció manual

1. Informa l’empresa i el tipus d’abast de la fitxa.
2. Al camp **«Plantilla d’homologació»**, selecciona una plantilla de la mateixa empresa i abast. La categoria del producte no limita aquesta selecció manual.
3. En seleccionar-la, s’incorporen els seus requisits i controls. Revisa les línies i desa la fitxa.

La selecció queda desada i es manté encara que canviïs el producte, el proveïdor, el nom o el codi, sempre que l’empresa i l’abast continuïn sent compatibles. Si canvies l’empresa o l’abast i la plantilla ja no correspon, el selector es buida i es torna al criteri automàtic. Les línies existents es conserven.

Per tornar a la selecció automàtica, buida el camp. Aquesta acció pot afegir els controls de la plantilla automàtica corresponent, però no elimina els que s’havien incorporat manualment. Els usuaris de fitxes tècniques poden consultar i seleccionar plantilles; modificar-ne la configuració continua reservat als administradors.

### Selecció automàtica

La selecció automàtica necessita que la fitxa tingui **empresa, tipus d’abast i producte intern**. Encara que el tipus d’abast permeti fitxes sense producte, sense producte intern no es selecciona automàticament cap plantilla.

El sistema segueix aquest criteri:

1. Busca plantilles actives de la mateixa empresa i tipus d’abast.
2. Comprova quines categories són aplicables al producte, incloses les categories ascendents.
3. Prioritza la plantilla amb la categoria aplicable més profunda de la jerarquia.
4. Si no hi ha cap plantilla amb categoria aplicable, utilitza la general sense categoria, si existeix.
5. En cas d’empat entre categories igualment profundes, tria la plantilla amb l’identificador intern més baix.

**Se selecciona una sola plantilla.** La plantilla específica no incorpora automàticament els requisits de la general: cal incloure-hi tots els controls que vulguis preparar.

La selecció es pot executar en editar dades de la fitxa, com el producte, el producte del proveïdor o el tipus d’abast. La plantilla triada automàticament no s’escriu al selector manual: aquest queda buit mentre s’utilitza el criteri automàtic.

### Exemple pràctic

Configures aquestes dues plantilles per a la mateixa empresa:

| Plantilla | Abast | Categoria | Requisits d’exemple |
|---|---|---|---|
| Matèries primeres general | Matèria primera | Sense categoria | Fitxa tècnica i qüestionari del proveïdor. |
| Homologació de farines | Matèria primera | Farines | Fitxa tècnica, qüestionari del proveïdor i declaració d’al·lèrgens. |

En preparar una fitxa nova d’un producte de la categoria «Farines», s’aplica la plantilla específica i s’afegeixen els tres requisits amb l’estat «Falta». Si la plantilla també inclou un certificat o una analítica, se’n preparen les línies corresponents.

Després completes cada apartat amb la documentació i els resultats del proveïdor. Aplicar la plantilla no aprova la fitxa ni acredita que els documents ja s’hagin rebut.

### Què passa si la fitxa ja té dades

L’aplicació conserva les línies existents i afegeix les que falten. Comprova els requisits pel tipus, els certificats per l’esquema, les analítiques pel nom del tipus i els assajos de migració pel tipus d’assaig.

En les conformitats d’envasos, evita afegir una línia si la plantilla té una referència informada que ja existeix a la fitxa. **Si la referència de la plantilla és buida, cada nova aplicació pot afegir una altra línia de conformitat.**

No sobreescriu els valors de les línies que ja identifica com a existents. Tampoc elimina controls perquè hagin desaparegut de la plantilla o perquè canviïs el producte o l’abast de la fitxa. Per això, després d’aquests canvis, cal revisar que les línies conservades continuïn sent aplicables.

Modificar una plantilla no actualitza de cop totes les fitxes existents. Si posteriorment torna a aplicar-se a una fitxa, hi pot afegir els controls nous, però conserva els ja existents.

### Crear una plantilla a partir d’una fitxa

El botó **«Crear plantilla»** utilitza l’empresa, el tipus d’abast i una categoria del producte de la fitxa. Prioritza la categoria directa més profunda; si no hi ha categories directes, consulta les categories disponibles amb els seus ascendents. Si no n’hi ha cap, utilitza la categoria buida.

Si ja existeix una plantilla amb aquesta combinació, hi afegeix els controls que falten. Si no existeix, en crea una amb el nom de la fitxa. Recupera els tipus de requisit, esquemes, tipus d’anàlisi i d’assaig, i la configuració de les conformitats d’envasos, incloses les referències i la normativa declarada.

No copia els PDF, les versions ni els resultats del proveïdor. Abans de reutilitzar-la, convé revisar que les referències i els controls recuperats siguin adequats per a les altres fitxes.

### Què queda fora de la plantilla

Les plantilles no generen registres sanitaris, declaracions detallades d’al·lèrgens, orígens dels ingredients ni especificacions físiques dels envasos. Tampoc assignen la família d’envasos ni aporten adjunts.

Aquests apartats es completen a cada fitxa segons el producte i la documentació del proveïdor. La revisió documental i la decisió d’aprovar l’homologació continuen sent passos separats.

Referència de la implementació: `tryton/trytond/trytond/modules/supplier_compliance/compliance.py`, model `ComplianceTemplate`, models de línies de plantilla i mètodes `_apply_compliance_template` i `create_template` de `Record`.

## 7. Registres d’homologació («Registros de homologación»)

El registre d’homologació és **la fitxa central on gestiones un article o servei d’un proveïdor, la seva documentació i la decisió d’autoritzar-ne l’ús** dins d’una empresa.

Un proveïdor pot tenir diverses fitxes, per exemple una per cada matèria primera o envàs que subministra. Un mateix producte intern també pot tenir fitxes per a diferents proveïdors, cadascuna amb la seva documentació i estat.

### Per a què serveixen

1. **Identificar què s’homologa i de quin proveïdor.** Relacionen l’empresa, el proveïdor, el producte i el tipus d’abast.
2. **Centralitzar la informació tècnica i documental.** Reuneixen requisits, certificats, dades alimentàries i dades d’envasos.
3. **Registrar la decisió d’homologació.** Permeten indicar si l’article està en preparació, aprovat, condicionat, suspès, caducat, donat de baixa o rebutjat.
4. **Fer seguiment de revisions i renovacions.** Mostren indicadors calculats a partir de les dates dels documents i controls.
5. **Consultar l’impacte en compres i existències.** Inclouen accessos a compres relacionades i l’estoc del producte intern.

### Camps principals

| Camp | Per a què serveix |
|---|---|
| Empresa | Empresa propietària de la fitxa. Obligatori. |
| Proveïdor | Proveïdor de l’article o servei. Obligatori. |
| Tipus d’abast | Classifica què s’homologa, per exemple matèria primera, envàs o servei. Obligatori. |
| Plantilla d’homologació | Selecció manual opcional, amb prioritat sobre la plantilla automàtica. Si queda buida, s’utilitza el criteri automàtic. |
| Producte | Producte intern al qual correspon la fitxa. És obligatori si ho exigeix el tipus d’abast. |
| Producte del proveïdor | Relació de compra entre el producte i el proveïdor, amb les seves referències comercials. |
| Codi | Referència interna o del proveïdor per identificar l’article. |
| Nom | Nom de la fitxa o de l’article homologat. Obligatori. |
| Nom extern de l’article | Denominació que utilitza el proveïdor quan difereix de la interna. |
| Data d’inici i data de finalització | Dates de la vigència prevista de l’homologació. |
| Actiu | Indica si el registre està actiu. És independent de l’estat d’homologació. |
| Estat | Decisió operativa actual, que es modifica amb els botons de la fitxa. |

Seleccionar un producte del proveïdor pot completar el proveïdor, el producte intern i, si són buits, el codi i els noms. També pot aplicar la plantilla corresponent. Cal comprovar que la referència seleccionada sigui la correcta abans de guardar.

El sistema comprova que el producte del proveïdor sigui coherent amb el proveïdor i el producte de la fitxa, i que la data de finalització no sigui anterior a la d’inici quan s’informen totes dues.

### Apartats de la fitxa

| Apartat | Contingut |
|---|---|
| Requisits | Documents i declaracions demanats, amb el seu estat, versions, dates i adjunts de cada versió. |
| Certificats | Certificacions del proveïdor registrades per esquema, amb número, emissor, abast, dates i versions. |
| Alimentació | Registres sanitaris, declaracions d’al·lèrgens, orígens dels ingredients i analítiques. |
| Envasos | Família d’envasos, especificacions tècniques, declaracions de conformitat i assajos de migració. |
| Baixa | Data i motiu de baixa, usuari autoritzador i possible article substitut. |
| Notes | Observacions generals, condicions d’ús o qüestions pendents. |
| Contactes | Contactes del proveïdor marcats per a alertes o crisis. |
| Adjunts | Documents generals vinculats directament a la fitxa. |
| Historial d’estats | Estat anterior i nou, data i hora del canvi i usuari que l’ha fet. |

Els apartats es completen segons el cas: una fitxa d’un servei no necessita les mateixes dades que una farina o una bossa. Els contactes provenen del proveïdor; no són una agenda independent de cada fitxa.

### Estats de l’homologació

| Estat | Ús habitual | Indicador «Compra bloquejada» en una fitxa activa |
|---|---|---|
| Borrador | Fitxa en preparació. És l’estat inicial. | Sí |
| Pendent de documentació | Falta rebre o revisar informació. | Sí |
| Aprovat | S’ha autoritzat l’ús de l’article. | No |
| Condicionat | S’ha autoritzat l’ús amb condicions que cal documentar. | No |
| Suspès | S’ha suspès temporalment l’autorització. | Sí |
| Caducat | S’ha decidit marcar l’homologació com a caducada. | Sí |
| Baixa | S’ha retirat l’article de l’ús autoritzat. | Sí |
| Rebutjat | No s’ha acceptat l’homologació. | Sí |

Els botons permeten canviar l’estat sense imposar un recorregut obligatori. **Aprovar no comprova automàticament que tots els documents estiguin complets i vigents.** La revisió correspon a l’usuari. Les condicions escrites a les notes tampoc es converteixen automàticament en restriccions de compra.

### Caducitats i indicadors de seguiment

- **Caducat:** indica que la data de finalització de la fitxa ja ha passat.
- **Documents caducats:** resumeix la caducitat de la mateixa fitxa o dels requisits, certificats, registres sanitaris i conformitats d’envasos, i les revisions vençudes d’analítiques i assajos de migració.
- **Necessita revisió:** en la implementació actual coincideix amb l’indicador de documents caducats; no és una comprovació de tots els documents que falten.
- **Sol·licitar actualització:** indica que algun dels documents o controls gestionats ha entrat en el seu termini d’avís.
- **Compra bloquejada:** depèn de l’estat i de si el registre està actiu; no es calcula directament a partir de les dates dels documents.

Els indicadors no canvien automàticament l’estat. Una fitxa pot continuar en estat «Aprovat» encara que tingui documentació caducada o una data de finalització passada. Informar dates o dies d’avís tampoc programa per si sol enviaments de correu.

### Com intervé en les compres

El mòdul comprova les línies amb producte quan la compra passa a pressupost. El comportament es configura per empresa a la configuració de compres:

| Mode | Comportament quan es troba una fitxa que bloqueja la compra |
|---|---|
| Cap | No aplica el control d’homologació. |
| Avís | Mostra un avís que l’usuari pot acceptar per continuar. |
| Bloqueig | Impedeix continuar. És el valor per defecte del mòdul. |

Per trobar la fitxa, busca registres actius de l’empresa, proveïdor i producte. Prioritza la coincidència amb el producte del proveïdor de la línia; si no la troba, utilitza la fitxa quan només n’hi ha una de candidata.

**Si no troba cap fitxa, o hi ha diverses candidates sense una coincidència que pugui seleccionar, aquest control no bloqueja la compra per manca d’homologació.** Tampoc revisa directament la documentació caducada: comprova l’estat de la fitxa seleccionada.

Una fitxa inactiva mostra «Compra bloquejada» a la seva fitxa, però la cerca de compres només selecciona registres actius. Per tant, desactivar una fitxa no equival a bloquejar les compres d’aquell producte i proveïdor. Per representar una suspensió o una baixa dins d’aquest control, cal gestionar l’estat de la fitxa activa i el mode de compres.

### Compres relacionades i estoc

La fitxa inclou comptadors i botons per consultar:

- **Compres obertes afectades:** compres en borrador, pressupost, confirmades o en procés.
- **Compres en borrador:** compres en borrador o pressupost.
- **Compres pendents de recepció:** compres confirmades o en procés que encara no consten com a rebudes.
- **Compres passades:** compres finalitzades, o en procés que ja consten com a rebudes.

La relació es determina pel producte del proveïdor o, si no està informat, pel proveïdor i producte intern, dins de l’empresa. Els comptadors indiquen el nombre de compres, no el nombre de línies.

**Estoc existent** mostra la quantitat del producte intern en el context de consulta i empresa. No identifica exclusivament les unitats comprades a aquell proveïdor ni certifica quins lots estan coberts per la documentació.

### Baixa i article substitut

El botó «Baixa» posa la data del dia i l’usuari actual com a autoritzador. Pots informar el motiu i seleccionar una altra fitxa activa de la mateixa empresa i abast, en estat aprovat o condicionat, com a substitut.

El substitut es pot mostrar al missatge del control de compres. **No substitueix automàticament el producte de les comandes ni modifica les compres ja existents.** Les compres relacionades permeten consultar l’impacte i decidir les actuacions necessàries.

### Exemple pràctic

Vols homologar una farina d’un proveïdor:

1. Crees una fitxa amb l’empresa, el proveïdor, l’abast «Matèria primera», el producte intern i la seva referència de proveïdor.
2. La plantilla aplicable prepara, per exemple, els requisits de fitxa tècnica i declaració d’al·lèrgens. Revises les línies i poses la fitxa en estat «Pendent de documentació».
3. Quan reps els documents, els registres a les versions corresponents, hi adjuntes els PDF i informes les dates. Completes els al·lèrgens, orígens o altres controls aplicables.
4. Després de revisar la informació, marques els requisits segons correspongui i poses la fitxa en estat «Aprovat».
5. Més endavant, els indicadors permeten detectar renovacions properes o dates vençudes. Registres les noves versions i revises si cal mantenir o canviar l’estat de l’homologació.
6. Si decideixes retirar l’article, el poses de baixa, informes el motiu i consultes les compres obertes. Si escau, indiques una fitxa substituta.

Aquest és un exemple de treball; el sistema no obliga a seguir tots aquests estats ni pren la decisió d’aprovació per l’usuari.

### Versions i historial

Per renovar documents, utilitza les versions dels requisits, certificats, registres sanitaris, orígens, analítiques, conformitats o assajos que disposen d’aquest mecanisme. Això permet conservar revisions anteriors i els seus adjunts. Els al·lèrgens i les especificacions físiques d’envasos no tenen versions pròpies.

L’historial d’estats registra la creació amb l’estat inicial i els canvis posteriors d’estat. No és un historial complet de totes les modificacions de camps o documents.

El botó «Crear plantilla» permet reutilitzar l’estructura de controls d’una fitxa, tal com s’explica a l’apartat anterior, sense copiar els documents ni els resultats del proveïdor.

Referència de la implementació: `tryton/trytond/trytond/modules/supplier_compliance/compliance.py`, models `Record` i `RecordStateHistory`; `view/record_form.xml`, `purchase.py` i `configuration.py` del mateix mòdul.
