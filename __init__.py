# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool

from . import compliance, configuration, food, packaging, party, product, purchase


def register():
    Pool.register(
        compliance.ScopeType,
        compliance.RequirementType,
        compliance.Scheme,
        compliance.ComplianceTemplate,
        compliance.ComplianceTemplateRequirement,
        compliance.ComplianceTemplateCertificate,
        compliance.ComplianceTemplateFoodAnalysis,
        compliance.ComplianceTemplatePackagingCompliance,
        compliance.ComplianceTemplatePackagingMigrationTest,
        compliance.Record,
        compliance.RecordStateHistory,
        compliance.Requirement,
        compliance.RequirementVersion,
        compliance.Certificate,
        compliance.CertificateVersion,
        configuration.Configuration,
        configuration.ConfigurationSupplierCompliance,
        food.FoodAllergenType,
        food.FoodHealthRegistration,
        food.FoodHealthRegistrationVersion,
        food.FoodAllergen,
        food.FoodOrigin,
        food.FoodOriginVersion,
        food.FoodAnalysis,
        food.FoodAnalysisVersion,
        packaging.PackagingFamily,
        packaging.PackagingSpecification,
        packaging.PackagingCompliance,
        packaging.PackagingComplianceVersion,
        packaging.PackagingMigrationTest,
        packaging.PackagingMigrationTestVersion,
        party.Party,
        party.ContactMechanism,
        product.Template,
        purchase.Purchase,
        purchase.ProductSupplier,
        purchase.Line,
        module='supplier_compliance', type_='model')
