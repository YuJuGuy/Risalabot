from django.shortcuts import render



def bot(request, context=None):
    return render(request, 'base/staticbot.html', context)