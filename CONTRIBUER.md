# Contribuer des données pour votre commune

> **Première version.** Ce guide est encore un brouillon. Nous découvrirons
> sans doute que certaines choses que nous pensions simples ne le sont pas :
> excusez-nous d'avance si votre contribution demande quelques allers-retours
> entre nous. Nous ferons de notre mieux pour réduire votre travail au
> minimum, car nous savons que la collecte des données est la partie la plus
> difficile de ce genre de projet.

Vous aimeriez voir votre commune, votre quartier ou votre métropole dans
l'observatoire ? Ce guide explique quelles informations nous sont utiles et
sous quelle forme nous les envoyer. Il n'est pas nécessaire d'être
informaticien : si vous savez remplir un tableur ou placer des points sur une
carte en ligne, vous pouvez contribuer.

En cas de doute, envoyez-nous ce que vous avez et posez-nous la question :
des données imparfaites accompagnées d'explications valent mieux que pas de
données du tout.

## En bref

Pour calculer combien de places de stationnement se trouvent à moins de 5 m
d'un passage piéton, il nous faut deux choses :

1. **les passages piétons** : où ils se trouvent ;
2. **les places de stationnement** : où elles se trouvent et de quel type
   elles sont (payantes, gratuites, livraison, PMR…).

Tout le reste est facultatif. Nous nous occupons nous-mêmes du sens de
circulation et du nom des rues (tirés d'OpenStreetMap), ainsi que des
limites des communes.

## Première étape : les données existent peut-être déjà

Avant de vous lancer dans un relevé, vérifiez si votre collectivité publie
déjà ces données en accès libre (« open data ») :

- sur le portail open data de votre ville ou de votre métropole, s'il
  existe : cherchez « passages piétons », « traversées piétonnes »,
  « stationnement », « emplacements », « aires de livraison », « places
  PMR » ;
- sur [data.gouv.fr](https://www.data.gouv.fr/), avec les mêmes mots-clés et
  le nom de votre commune.

Si vous trouvez quelque chose, **le plus simple est de nous envoyer le
lien** vers la page du jeu de données : nous saurons le télécharger. C'est
ainsi qu'a été construite la carte de Nantes Métropole, à partir de
[data.nantesmetropole.fr](https://data.nantesmetropole.fr/).

Si ces données ne sont pas publiées, vous pouvez aussi les demander à votre
mairie : beaucoup de services de voirie tiennent un inventaire sans le
mettre en ligne.

## Les passages piétons

Pour chaque passage piéton, il nous faut sa position. Par ordre de
préférence :

- **un trait** tracé en travers de la rue, d'un trottoir à l'autre : c'est
  le plus précis, car il indique l'orientation du passage ;
- **un point** au milieu du passage : c'est utilisable, nous retrouverons
  l'orientation de la rue, mais le résultat sera un peu moins précis.

Informations facultatives, mais bienvenues :

- le type de marquage (peinture blanche, résine, clous ou autre) ;
- la présence d'une bande d'éveil de vigilance (les dalles podotactiles
  pour les personnes aveugles ou malvoyantes) ;
- la présence d'un îlot central (refuge au milieu de la chaussée).

## Les places de stationnement

Pour chaque emplacement, il nous faut sa position, sous l'une de ces formes
(par ordre de préférence) :

- **le contour** de la place ou de la rangée de places (un petit
  rectangle) ;
- **un trait** le long du trottoir, de la première à la dernière place de
  la rangée, en précisant si les places sont **en long** (le long du
  trottoir), **en épi** ou **en bataille** ;
- **un point** : cela convient bien pour une place isolée (place PMR, par
  exemple) ou une aire de livraison, dont il faut alors indiquer la
  longueur. Pour une rangée de plusieurs places, un trait est nettement
  plus fiable.

Et pour chaque emplacement, **sa catégorie**, avec vos propres mots si
besoin. Par exemple :

- payant (avec la zone tarifaire si elle existe) ;
- gratuit ;
- aire de livraison ;
- place PMR (personnes à mobilité réduite) ;
- deux-roues motorisés ;
- réservé : taxis, arrêt minute, ambulances, autre (précisez).

Les places vélos et trottinettes ne sont pas comptées par l'observatoire,
la loi les autorisant près des passages : inutile de les relever. Si elles figurent déjà dans vos données,
laissez-les, nous les écarterons.

Si les catégories sont dans des fichiers séparés (un fichier pour le
payant, un pour les livraisons…), c'est très bien aussi : dites-nous
simplement ce que contient chaque fichier.

## Le territoire

Indiquez-nous la ou les communes couvertes. Si vous souhaitez que la carte
affiche aussi des **quartiers**, envoyez-nous leur découpage (une carte des
contours) ou le lien où le trouver. Sinon, la carte se limitera aux
communes.

Si vos données ne couvrent qu'une partie du territoire (un quartier, le
centre-ville), dites-le-nous : nous l'indiquerons sur la carte pour que
personne ne conclue à tort qu'il n'y a rien ailleurs.

## Les formats que nous acceptons

Nous savons lire la plupart des formats courants. Envoyez les fichiers tels
que votre logiciel ou votre portail les produit, sans les retravailler.

| Format | Quand l'utiliser |
| --- | --- |
| **Lien vers un portail open data** | Les données sont déjà publiées. C'est le plus simple. |
| **GeoJSON** (`.geojson`, `.json`) | Format cartographique le plus courant sur le web ; proposé par la plupart des portails open data et par [uMap](https://umap.openstreetmap.fr/). |
| **GeoPackage** (`.gpkg`) | Fichier unique produit par QGIS et la plupart des logiciels de cartographie. |
| **Shapefile** (`.shp`) | Format historique des logiciels de cartographie. Il se compose de plusieurs fichiers (`.shp`, `.shx`, `.dbf`, `.prj`…) : envoyez-les **tous**, réunis dans un fichier `.zip`. |
| **KML / KMZ** | Exports de Google My Maps, Google Earth ou uMap. |
| **Tableur** (`.csv`, `.xlsx`, `.ods`) | Une ligne par passage ou par emplacement, avec des colonnes pour la position (voir ci-dessous). |

Un ensemble de plusieurs fichiers (par exemple un fichier CSV par
catégorie de stationnement) nous convient tout à fait.

### Si vous utilisez un tableur

Mettez une ligne par passage piéton (ou par emplacement) et une colonne par
information. La position se donne en deux colonnes, **latitude** et
**longitude**, telles que vous les obtenez par un clic droit sur un point
dans Google Maps ou sur [openstreetmap.org](https://www.openstreetmap.org/)
(par exemple `47.218371` et `-1.553621`).

Exemple pour les passages piétons :

| latitude | longitude | marquage | bande_eveil | ilot | remarque |
| --- | --- | --- | --- | --- | --- |
| 47.218371 | -1.553621 | blanc | oui | non | |
| 47.219042 | -1.551876 | résine | non | oui | devant l'école |

Exemple pour le stationnement :

| latitude | longitude | categorie | nb_places | longueur_m | disposition | remarque |
| --- | --- | --- | --- | --- | --- | --- |
| 47.218402 | -1.553580 | PMR | 1 | | en long | |
| 47.219110 | -1.551790 | livraison | | 12 | | |

Les noms de colonnes sont libres : nous les adapterons. Quelques conseils
tout de même :

- placez les points en zoomant au maximum : la mesure se joue au mètre
  près ;
- gardez une seule information par colonne ;
- utilisez toujours les mêmes mots dans une colonne (« payant » partout,
  plutôt que « payant », « Payant » et « P ») ;
- si vos positions ne sont pas en latitude et longitude (par exemple des
  coordonnées « Lambert 93 », courantes dans les données des
  collectivités), c'est possible : indiquez-nous simplement le système
  utilisé si vous le connaissez.

### Si vous faites le relevé vous-même

[uMap](https://umap.openstreetmap.fr/) est un outil en ligne gratuit, en
français, qui permet de tracer des points, des traits et des contours sur
une carte, puis de l'exporter en GeoJSON ou en KML. Créez par exemple un
calque « Passages piétons » et un calque par catégorie de stationnement.

Une autre possibilité, utile à tous au-delà de cet observatoire, est
d'ajouter les passages piétons directement dans
[OpenStreetMap](https://www.openstreetmap.org/). Prévenez-nous si vous le
faites.

## Ce qui est difficile à utiliser

- **Les plans en PDF, les photos et les scans** : ils doivent être
  redessinés à la main. Si c'est tout ce qui existe, contactez-nous avant
  pour en parler.
- **Les positions approximatives** (« vers le n° 12 ») : la mesure se joue
  à quelques mètres près, il nous faut des positions sur la carte.

## Droits et licence

Nous publions les données utilisées sous une licence libre. Précisez-nous
donc :

- **la source** des données (votre collectivité, votre association, vous
  personnellement…) et la façon dont vous souhaitez être cité ;
- **la licence**, si les données viennent d'un portail open data (souvent
  la Licence Ouverte Etalab ou l'ODbL) ;
- **votre accord** pour leur publication, si vous les avez produites
  vous-même ;
- **la date** du relevé ou de l'extraction, même approximative.

N'envoyez pas de données personnelles : pas de plaques d'immatriculation,
pas de photos où l'on reconnaît des personnes.

## Envoyer vos données

Écrivez-nous en passant par le site de
[Rue Commune](https://www.rue-commune.org/). Dans votre message,
indiquez :

- la commune ou le territoire couvert, et s'il est couvert en entier ;
- les fichiers joints ou les liens, et ce que contient chacun ;
- la source, la licence ou votre accord de publication, et la date ;
- comment vous joindre si nous avons des questions.

Si les fichiers sont trop lourds pour une pièce jointe, un lien de
téléchargement (par exemple via un service de transfert de fichiers) fait
très bien l'affaire.

Merci pour votre contribution !
