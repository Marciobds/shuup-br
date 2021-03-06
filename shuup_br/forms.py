# -*- coding: utf-8 -*-
# This file is part of Shuup BR.
#
# Copyright (c) 2016, Rockho Team. All rights reserved.
# Author: Christian Hess
#
# This source code is licensed under the AGPLv3 license found in the
# LICENSE file in the root directory of this source tree.

from shuup_br.base import CNPJ, CPF
from shuup_br.models import CompanyInfo, ESTADOS_CHOICES, ExtraMutableAddress, PersonInfo, Taxation
from shuup_br.utils import get_only_digits, get_sample_datetime

from shuup.core.models._addresses import MutableAddress
from shuup.core.models._contacts import Gender
from shuup.core.utils.forms import MutableAddressForm

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.utils import formats
from django.utils.functional import lazy
from django.utils.translation import ugettext_lazy as _


def get_date_format():
    return formats.get_format_lazy('DATE_INPUT_FORMATS')[0]\
        .replace("%Y", "0000")\
        .replace("%y", "0000")\
        .replace("%d", "00")\
        .replace("%m", "00")


def PhoneValidator(phone):
    length = len(get_only_digits(phone))

    # 8 ou 9 digitos com dd
    if not 10 <= length <= 11:
        raise ValidationError(_("Invalid phone number"))


def OptionalPhoneValidator(phone):
    if phone:
        PhoneValidator(phone)


class ShuupBRMutableAddressForm(MutableAddressForm):
    name = forms.CharField(label=_('Destinatário'))
    phone = forms.CharField(label=_('Telefone'), required=True, validators=[PhoneValidator])
    postal_code = forms.CharField(label=_('CEP'), required=True)
    street2 = forms.CharField(label=_('Complemento'), required=False)
    street3 = forms.CharField(label=_('Bairro'), required=True)
    region = forms.ChoiceField(label=_('Estado'), required=True, choices=ESTADOS_CHOICES)
    numero = forms.CharField(label=_('Número'), required=True)
    cel = forms.CharField(label=_('Celular'), required=False, validators=[OptionalPhoneValidator])
    ponto_ref = forms.CharField(label=_('Ponto de referência'), required=False)

    class Meta:
        model = MutableAddress
        fields = (
            "name", "postal_code", "street", "numero",
            "street2", "street3", "ponto_ref",
            "city", "region", "country", "phone", "cel"
        )
        widgets = {
            'country': forms.HiddenInput(),
        }

    def __init__(self, instance=None, *args, **kwargs):
        initial = kwargs.pop('initial', {})

        if instance and hasattr(instance, 'extra'):
            initial.update(model_to_dict(instance.extra))

        super(ShuupBRMutableAddressForm, self).__init__(initial=initial,
                                                        instance=instance,
                                                        *args, **kwargs)

    def save(self, commit=True):
        instance = super(ShuupBRMutableAddressForm, self).save(commit)

        if commit:
            extra_addr = ExtraMutableAddress.objects.get_or_create(address=instance)[0]
            extra_addr.numero = self.cleaned_data['numero']
            extra_addr.cel = self.cleaned_data['cel']
            extra_addr.ponto_ref = self.cleaned_data['ponto_ref']
            extra_addr.full_clean()
            extra_addr.save()

        return instance


class PersonInfoForm(forms.ModelForm):

    class Meta:
        model = PersonInfo
        fields = ['name', 'cpf', 'rg', 'birth_date', 'gender']
        widgets = {
            'birth_date': forms.DateInput(attrs={'placeholder': lazy(get_sample_datetime, str)(),
                                                 'data-mask': lazy(get_date_format, str)()}),
        }
        localized_fields = ('birth_date',)
        prefix = 'person'

    def clean_cpf(self):
        cpf = self.cleaned_data['cpf']

        if not CPF.validate(cpf):
            raise forms.ValidationError(_("CPF inválido"))
        return cpf

    def clean_gender(self):
        gender = self.cleaned_data['gender']

        # Se for do tipo Gender, então pega só o valor
        # e não a classe toda...
        if type(gender) == Gender:
            return gender.value
        return gender


class CompanyInfoForm(forms.ModelForm):

    class Meta:
        model = CompanyInfo
        fields = ['name', 'cnpj', 'ie', 'im', 'taxation', 'responsible']

    def clean_taxation(self):
        taxation = self.cleaned_data['taxation']

        # Se for do tipo Taxation, então pega só o valor
        # e não a classe toda...
        if type(taxation) == Taxation:
            return taxation.value
        return taxation

    def clean_cnpj(self):
        cnpj = self.cleaned_data['cnpj']

        if not CNPJ.validate(cnpj):
            raise forms.ValidationError(_("CNPJ inválido"))
        return cnpj

    def clean(self):
        cleaned_data = super(CompanyInfoForm, self).clean()
        taxation = cleaned_data.get('taxation')

        # quando for contribuinte do ICMS, inscrição estadual é obrigatória
        if taxation == Taxation.ICMS.value and not cleaned_data.get('ie'):
            self.add_error('ie', _("A Inscrição Estadual é obrigatória quando for contribuinte do ICMS."))
        elif taxation == Taxation.ISENTO.value:
            cleaned_data['ie'] = 'ISENTO'
        elif taxation == Taxation.NAO_CONTRIBUINTE.value:
            cleaned_data['ie'] = ''

        return cleaned_data
