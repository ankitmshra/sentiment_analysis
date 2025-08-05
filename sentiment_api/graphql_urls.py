"""
GraphQL URL configuration for sentiment_api app.

This module contains GraphQL endpoint configuration with GraphiQL playground.
"""

from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView
from .schema import schema

app_name = "sentiment_graphql"

urlpatterns = [
    # GraphQL endpoint with GraphiQL playground
    path(
        "",
        csrf_exempt(GraphQLView.as_view(graphiql=True, schema=schema)),
        name="graphql",
    ),
    # Alternative endpoint without GraphiQL (for production)
    path(
        "api/",
        csrf_exempt(GraphQLView.as_view(graphiql=False, schema=schema)),
        name="graphql_api",
    ),
]
