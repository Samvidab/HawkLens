"""GraphQL query documents, written from the confirmed introspection schema
(data/matterport/schema.json). No field is guessed.
"""

# Paginated model search. offset is a STRING cursor (nextOffset); pageSize is Int.
# Returns search-result fields (thumbnail + address + published live here).
MODELS_SEARCH = """
query ModelsSearch($query: String, $pageSize: Int, $offset: String) {
  models(query: $query, pageSize: $pageSize, offset: $offset) {
    totalResults
    nextOffset
    results {
      id
      name
      created
      modified
      demo
      address {
        locality
        administrativeArea
        postalCode
        countryCode
        address
      }
      geolocation { lat long }
      image { url }
      publication { published }
    }
  }
}
"""

# Full model by id — the Showcase embed + show URL live on the full Model.
MODEL_BY_ID = """
query ModelById($id: ID!) {
  model(id: $id) {
    id
    name
    created
    modified
    address {
      locality
      administrativeArea
      postalCode
      countryCode
      address
    }
    geocoordinates { latitude longitude }
    image { url }
    publication { embed url published }
  }
}
"""
