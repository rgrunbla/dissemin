import pytest

from deposit.models import DepositRecord
from upload.models import UploadedPDF


@pytest.fixture
def uploaded_pdf(user_leibniz):
    """
    A simple uploaded pdf of user leibniz. The file does not exist.
    """
    pdf = UploadedPDF.objects.create(
        user=user_leibniz,
        file='uploaded_pdf.pdf',
    )
    return pdf

@pytest.fixture
def deposit_record(request, db, book_god_of_the_labyrinth, authenticated_client, dummy_repository, uploaded_pdf):
    """
    A simple deposit record with all necessary data
    """
    dummy_repository.letter_declaration = 'test_pdf_generator'
    dummy_repository.save()
    dr = DepositRecord.objects.create(
        paper=book_god_of_the_labyrinth,
        user=authenticated_client.user,
        repository=dummy_repository,
        status='pending',
        file=uploaded_pdf,
    )

    request.cls.dr = dr
    request.cls.client = authenticated_client
