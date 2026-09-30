from django.db import models


class Institution(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Account(models.Model):
    class Type(models.TextChoices):
        CHEQUING = "chequing"
        SAVINGS = "savings"
        CREDIT_CARD = "credit_card"
        TFSA = "tfsa"
        RRSP = "rrsp"
        FHSA = "fhsa"
        BROKERAGE = "brokerage"
        LOAN = "loan"
        OTHER = "other"

    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=Type.choices)
    currency = models.CharField(max_length=3, default="CAD")
    is_liability = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.institution} - {self.name}"


class Category(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class ImportBatch(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    opening_cents = models.BigIntegerField()
    closing_cents = models.BigIntegerField()
    diff_cents = models.BigIntegerField(null=True)  # 0 means reconciled
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account} - {self.filename}"


class Transaction(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income"
        EXPENSE = "expense"
        TRANSFER = "transfer"
        CONTRIBUTION = "contribution"
        WITHDRAWAL = "withdrawal"
        DIVIDEND = "dividend"
        INTEREST = "interest"
        FEE = "fee"
        ADJUSTMENT = "adjustment"

    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    batch = models.ForeignKey(ImportBatch, null=True, blank=True, on_delete=models.SET_NULL)
    date = models.DateField()
    amount_cents = models.BigIntegerField()  # money in = positive, money out = negative
    description = models.CharField(max_length=500)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.EXPENSE)
    fingerprint = models.CharField(max_length=40, db_index=True)

    def __str__(self):
        return f"{self.date} {self.description} {self.amount_cents / 100:.2f}"