var RIGHTS = {
  "C001": {"content_id": "C001", "title": "Harbour Evening News", "regions": ["SG"], "rights_expiry": "2026-12-31", "editorial_owner": "News Desk"},
  "C007": {"content_id": "C007", "title": "Lion City Hearts", "regions": ["SG", "MY", "BN"], "rights_expiry": "2027-03-31", "editorial_owner": "Drama Production"},
  "C009": {"content_id": "C009", "title": "Merlion Mysteries", "regions": ["SG", "MY", "ID"], "rights_expiry": "2027-06-30", "editorial_owner": "Drama Production"},
  "C010": {"content_id": "C010", "title": "Hawker Love Story", "regions": ["SG", "TW"], "rights_expiry": "2027-01-15", "editorial_owner": "Mandarin Drama"}
};
var id = String(context.getVariable("proxy.pathsuffix")).split("/").pop().toUpperCase();
var r = RIGHTS[id];
context.setVariable("response.header.Content-Type", "application/json");
if (r) {
  context.setVariable("response.status.code", 200);
  context.setVariable("response.content", JSON.stringify(r));
} else {
  context.setVariable("response.status.code", 404);
  context.setVariable("response.content", JSON.stringify({"error": "unknown content_id", "content_id": id}));
}
