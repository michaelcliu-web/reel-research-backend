from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from papers.models import Paper


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_paper(request):
    pdf_file = request.FILES.get("pdf_file")
    if not pdf_file:
        return Response(
            {"error": "No PDF file provided"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not pdf_file.name.lower().endswith(".pdf"):
        return Response(
            {"error": "File must be a PDF"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    paper = Paper.objects.create(
        user=request.user,
        pdf_file=pdf_file,
        title=pdf_file.name.replace(".pdf", "").replace("_", " "),
    )

    return Response(
        {"paper_id": str(paper.id), "title": paper.title},
        status=status.HTTP_201_CREATED,
    )
