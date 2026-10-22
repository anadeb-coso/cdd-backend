"""Comptes créés dans le DCC (utilisateurs web et facilitateurs) : identifiant `prénom.nom`, mot de passe
initial généré et envoyé par e-mail, changement obligatoire à la première connexion sur toutes les plateformes
(DCC web et mobile, MGP web et mobile, SIG), et nouveau mot de passe appliqué à tous les comptes de la personne.

Une personne = ses comptes DCC de même e-mail (sans tenir compte de la casse) ou liés par `Facilitator.user`,
plus son compte MGP de même e-mail. L'obligation est rangée dans `PasswordChangeRequirement` (base partagée) :
le SIG la lit dans la même base, le MGP par sa connexion `mis` vers cette base. Tout changement de mot de passe
passe par le DCC (page Profil, mot de passe oublié, applications mobiles, pages de changement imposé du SIG et
du MGP), qui la lève pour la personne entière.
"""
import logging
import re
import secrets
import unicodedata
from datetime import datetime

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.db import connections, transaction
from django.db.models import Q
from django.template.loader import get_template
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

# Mot de passe généré : lettres et chiffres seulement (règles des applications mobiles et de
# usermanager.functions.validate_password), au moins une lettre et un chiffre, sans caractères ambigus
# (0/O, 1/l/I) ; le MGP refuse plus de 16 caractères à la connexion mobile.
PASSWORD_LETTERS = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
PASSWORD_DIGITS = '23456789'
PASSWORD_LENGTH = 10
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 16

# Plateformes où un changement de mot de passe peut être fait (`PasswordChangeRequirement.changed_on`).
PLATFORMS = ('dcc_web', 'dcc_mobile', 'mgp_web', 'mgp_mobile', 'sig_web', 'profile', 'password_reset')


# ---------------------------------------------------------------------------------------------
# Identifiant et mot de passe
# ---------------------------------------------------------------------------------------------

def generate_password(length=PASSWORD_LENGTH):
    alphabet = PASSWORD_LETTERS + PASSWORD_DIGITS
    while True:
        password = ''.join(secrets.choice(alphabet) for _i in range(length))
        if any(c.isalpha() for c in password) and any(c.isdigit() for c in password):
            return password


def _ascii_token(value):
    """« Kézié » -> « kezie » : minuscules sans accents, lettres, chiffres et tirets internes seulement."""
    value = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii').lower()
    value = re.sub(r'[^a-z0-9-]', '', value)
    return re.sub(r'-{2,}', '-', value).strip('-')


def name_tokens(value):
    """Prénoms (ou noms) séparés par des espaces ; un prénom composé (« Marie-Rita ») reste un seul prénom."""
    return [token for token in (_ascii_token(part) for part in re.split(r'[\s,;/]+', str(value or ''))) if token]


def split_full_name(name):
    """(noms, prénoms) d'un nom complet au format du DCC « NOM Prénoms » : le 1er mot est le nom (même découpage
    que `authentication.functions.ensure_facilitator_user`)."""
    parts = str(name or '').split()
    return (parts[0], ' '.join(parts[1:])) if parts else ('', '')


def username_taken(username):
    from authentication.models import Facilitator

    return (Facilitator.objects.filter(username__iexact=username).exists()
            or User.objects.filter(username__iexact=username).exists())


def username_candidates(first_names, last_names):
    """« un de ses prénoms POINT un de ses noms » : 1er prénom.1er nom, puis les autres combinaisons."""
    firsts, lasts = name_tokens(first_names), name_tokens(last_names)
    if firsts and lasts:
        return [f"{first}.{last}" for first in firsts for last in lasts]
    return firsts or lasts


def generate_username(first_names, last_names, reserved=()):
    """Premier identifiant `prénom.nom` libre, ni chez les facilitateurs ni chez les utilisateurs web (la connexion
    mobile cherche l'un puis l'autre, sans tenir compte de la casse) ; sinon le premier suivi d'un numéro (2, 3…).
    `reserved` : identifiants déjà attribués dans le même lot (import). None si le nom est vide."""
    reserved = {r.lower() for r in reserved}
    candidates = username_candidates(first_names, last_names)
    if not candidates:
        return None
    for candidate in candidates:
        if candidate not in reserved and not username_taken(candidate):
            return candidate
    number = 2
    while True:
        candidate = f"{candidates[0]}{number}"
        if candidate not in reserved and not username_taken(candidate):
            return candidate
        number += 1


def email_in_use(email, exclude_user_id=None):
    """E-mail déjà porté par un utilisateur web ou un facilitateur du DCC (sans tenir compte de la casse)."""
    from authentication.models import Facilitator

    email = (email or '').strip()
    if not email:
        return False
    users = User.objects.filter(email__iexact=email)
    if exclude_user_id:
        users = users.exclude(pk=exclude_user_id)
    return users.exists() or Facilitator.objects.filter(email__iexact=email).exists()


def validate_new_password(password, confirmation, current_password=None):
    """Liste des erreurs du nouveau mot de passe (vide = valide) : mêmes règles que les applications mobiles
    (lettres et chiffres, au moins une lettre et un chiffre, 8 caractères), 16 au plus (limite du MGP)."""
    errors = []
    password = password or ''
    if not password:
        return [_("The new password is required.")]
    if password != (confirmation or ''):
        errors.append(_("The confirmation password must be the same as the new password."))
    if not re.fullmatch(r'[A-Za-z0-9]+', password):
        errors.append(_("The password must contain only letters and numbers."))
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(_("The password must contain at least 8 characters."))
    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append(_("The password must contain at most 16 characters."))
    if not re.search(r'[A-Za-z]', password):
        errors.append(_("The password must contain at least one letter."))
    if not re.search(r'[0-9]', password):
        errors.append(_("The password must contain at least one digit."))
    if current_password and password == current_password:
        errors.append(_("The new password must be different from the current one."))
    return errors


# ---------------------------------------------------------------------------------------------
# Comptes d'une même personne
# ---------------------------------------------------------------------------------------------

def _email_key(email):
    return (email or '').strip().lower() or None


class Person:
    """Comptes DCC actifs d'une même personne et leurs e-mails (en minuscules)."""

    def __init__(self, users, facilitators):
        self.users = users
        self.facilitators = facilitators
        self.emails = sorted({key for key in (_email_key(a.email) for a in list(users) + list(facilitators)) if key})

    @property
    def exists(self):
        return bool(self.users or self.facilitators)

    def password_hashes(self):
        return [a.password for a in list(self.users) + list(self.facilitators) if a.password]


def person_accounts(account=None, login=None):
    """Comptes DCC actifs de la personne d'un compte (`User` ou `Facilitator`) ou d'un identifiant de connexion
    (e-mail ou nom d'utilisateur, sans tenir compte de la casse)."""
    from authentication.models import Facilitator

    users, facilitators = {}, {}
    if login:
        login = login.strip()
        lookup = Q(email__iexact=login) | Q(username__iexact=login)
        users.update({u.pk: u for u in User.objects.filter(lookup, is_active=True)})
        facilitators.update({f.pk: f for f in Facilitator.objects.filter(lookup, active=True)})
    elif isinstance(account, Facilitator):
        facilitators[account.pk] = account
    elif account is not None:
        users[account.pk] = account

    for _round in range(2):  # e-mails des comptes liés, puis comptes de ces e-mails
        emails = {key for key in (_email_key(a.email) for a in list(users.values()) + list(facilitators.values())) if key}
        email_q = Q(pk__in=[])
        for email in emails:
            email_q |= Q(email__iexact=email)
        for user in User.objects.filter(email_q | Q(facilitator__in=list(facilitators)), is_active=True):
            users.setdefault(user.pk, user)
        for facilitator in Facilitator.objects.filter(email_q | Q(user_id__in=list(users)), active=True):
            facilitators.setdefault(facilitator.pk, facilitator)
    return Person(list(users.values()), list(facilitators.values()))


def grm_account(email):
    """(id, empreinte du mot de passe) du compte MGP actif de cet e-mail, lu dans la base du MGP (connexion `grm`,
    comme usermanager/views.py), ou None."""
    if not email or 'grm' not in connections:
        return None
    try:
        with transaction.atomic(using='grm'), connections['grm'].cursor() as cursor:
            cursor.execute(
                "SELECT id, password FROM authentication_user WHERE lower(email) = lower(%s) AND is_active = TRUE "
                "ORDER BY id LIMIT 1",
                [email],
            )
            row = cursor.fetchone()
    except Exception as exc:  # base du MGP injoignable : seuls les comptes DCC comptent
        logger.warning("MGP account lookup failed: %s", exc)
        return None
    return {'id': row[0], 'password': row[1]} if row else None


# ---------------------------------------------------------------------------------------------
# Changement obligatoire à la première connexion
# ---------------------------------------------------------------------------------------------

def _requirements(person):
    from authentication.models import PasswordChangeRequirement

    lookup = Q(pk__in=[])
    if person.emails:
        lookup |= Q(email__in=person.emails)
    if person.users:
        lookup |= Q(user_id__in=[u.pk for u in person.users])
    if person.facilitators:
        lookup |= Q(facilitator_id__in=[f.pk for f in person.facilitators])
    return PasswordChangeRequirement.objects.filter(lookup)


def require_password_change(email=None, user=None, facilitator=None, created_by=None):
    """Le compte créé (et toute la personne) devra changer son mot de passe à la première connexion."""
    from authentication.models import PasswordChangeRequirement

    if created_by is not None and not getattr(created_by, 'is_authenticated', False):
        created_by = None
    return PasswordChangeRequirement.objects.create(
        email=_email_key(email), user=user, facilitator=facilitator, created_by=created_by,
    )


def password_change_required(account=None, login=None, person=None):
    person = person or person_accounts(account=account, login=login)
    return person.exists and _requirements(person).filter(changed_at__isnull=True).exists()


def mark_password_changed(person, platform):
    """Lève l'obligation pour toute la personne (le changement fait sur une plateforme vaut pour toutes)."""
    return _requirements(person).filter(changed_at__isnull=True).update(changed_at=timezone.now(), changed_on=platform)


def mark_password_changed_for_email(email, platform):
    """Après un changement de mot de passe par e-mail (page Profil, mot de passe oublié)."""
    if not email:
        return 0
    return mark_password_changed(person_accounts(login=email), platform)


def set_person_password(person, new_password, platform):
    """Nouveau mot de passe sur tous les comptes DCC de la personne (utilisateurs web, donc aussi le SIG, et
    facilitateurs) et sur son compte MGP, puis obligation levée. Renvoie {'mgp': True | False | None}
    (None : pas de compte MGP)."""
    from authentication.models import Facilitator
    import grm_client

    hashed = make_password(new_password)
    # `update` : ni signaux, ni nouveau hachage par Facilitator.save()
    User.objects.filter(pk__in=[u.pk for u in person.users]).update(password=hashed)
    Facilitator.objects.filter(pk__in=[f.pk for f in person.facilitators]).update(password=hashed)
    for account in list(person.users) + list(person.facilitators):
        account.password = hashed
    mark_password_changed(person, platform)

    sent = [bool(grm_client.set_grm_user_password(email, new_password))
            for email in person.emails if grm_account(email) is not None]
    return {'mgp': all(sent) if sent else None}


def change_initial_password(login, current_password, new_password, confirmation, platform, account=None):
    """Changement imposé à la première connexion, depuis n'importe quelle plateforme : l'identifiant (e-mail ou
    nom d'utilisateur) — ou le compte connecté (`account`, page web du DCC) — et le mot de passe actuel d'un des
    comptes de la personne (DCC, ou MGP de même e-mail) suffisent, sans code par e-mail (un facilitateur peut ne
    pas avoir d'e-mail). Refusé si aucun changement n'est en attente : les autres changements passent par la page
    Profil (code par e-mail). Renvoie (ok, erreurs, person)."""
    login = (login or '').strip()
    if (not login and account is None) or not current_password:
        return False, [_("You have to fill all the fields")], None
    person = person_accounts(account=account) if account is not None else person_accounts(login=login)
    hashes = person.password_hashes()
    for email in person.emails or ([login] if '@' in login else []):
        account = grm_account(email)
        if account and account['password']:
            hashes.append(account['password'])
    if not person.exists or not any(check_password(current_password, h) for h in hashes):
        return False, [_("Incorrect identifiers")], None
    if not password_change_required(person=person):
        return False, [_("Your password has already been changed.")], person
    errors = validate_new_password(new_password, confirmation, current_password)
    if errors:
        return False, errors, person
    set_person_password(person, new_password, platform if platform in PLATFORMS else 'dcc_web')
    return True, [], person


# ---------------------------------------------------------------------------------------------
# E-mails
# ---------------------------------------------------------------------------------------------

def send_mail_to(subject, template_path_without_extension, context, to):
    """Envoi direct à `to` seulement. Contrairement à cdd.my_librairies.mail.send_mail.send_email, aucune
    adresse n'est ajoutée en copie (ce mail peut contenir un mot de passe) ; en DEBUG, envoyé à
    RECIPIENT_EMAIL_DEFAULT comme les autres mails du DCC. Renvoie True si l'envoi a réussi."""
    if settings.DEBUG:
        to = [settings.RECIPIENT_EMAIL_DEFAULT]
    to = [address for address in to if address]
    if not to:
        return False
    try:
        message = EmailMultiAlternatives(
            subject, get_template(template_path_without_extension + '.txt').render(context), to=to,
        )
        message.attach_alternative(get_template(template_path_without_extension + '.html').render(context), "text/html")
        return bool(message.send())
    except Exception as exc:
        logger.warning("Mail '%s' not sent: %s", subject, exc)
        return False


def platform_links(facilitator=False):
    """Plateformes à présenter dans le mail des identifiants (adresses de l'environnement courant)."""
    links = [(_("DCC Web"), settings.CDD_URL_BASE, _("e-mail address"))]
    if facilitator:
        links.append((_("DCC mobile application"), f"{settings.CDD_URL_BASE}/fr/store-apps/", _("username")))
        links.append((_("MGP Web and mobile application"), settings.GRM_URL_BASE, _("e-mail address")))
    else:
        links.append((_("SIG Web"), settings.MIS_URL_BASE, _("e-mail address")))
    return [{'name': name, 'url': url, 'login_with': login_with} for name, url, login_with in links]


def send_account_credentials(full_name, email, username, password, facilitator=False, sex=None, localities=None):
    """Mail de bienvenue : adresse e-mail, nom d'utilisateur et mot de passe initial (à changer à la première
    connexion), plateformes accessibles et, pour un facilitateur, ses localités."""
    title = _("Your account has been created")
    context = {
        'subject': title,
        'title': title,
        'greeting': _("Hello"),
        'all_sex': sex or _("Mr./Mrs."),
        'user_full_name': full_name,
        'email': email,
        'username': username,
        'password': password,
        'facilitator': facilitator,
        'platforms': platform_links(facilitator),
        'localities': localities or [],
        'current_year': datetime.now().year,
    }
    subject = f"[COSO Apps : {datetime.now().strftime('%Y-%m-%d')}] {title}"
    return send_mail_to(subject, 'mail/send/account_credentials', context, [email])
