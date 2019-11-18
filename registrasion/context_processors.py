from registrasion.views import _staff_only

def registrasion(request):

    return {
        'registrasion_admin': _staff_only(request.user),
    }
