$f = "C:\Users\lenovo\.kiro\specs\python-url-shortener\design.md"
$c = Get-Content $f -Raw

$s = $c.IndexOf("| Property | Test file | What varies |")
$e = $c.IndexOf("**Hypothesis strategy notes:**")

$before = $c.Substring(0, $s)
$after = $c.Substring($e)

$newTable = "| Property | Test file | What varies |
|---|---|---|
| 1 - Short code generation correctness | ``test_code_generator.py`` | Any valid http/https URL; asserts format and short_url structure |
| 2 - Shortening idempotence | ``test_url_service.py`` | Valid URLs submitted multiple times; asserts same short_code returned |
| 3 - Redirect round-trip | ``test_url_service.py`` | Valid URLs; asserts 302 Location header matches original URL |
| 4 - Access count monotonically increases | ``test_url_service.py`` | K successive redirects (1-50); asserts count == N+K |
| 5 - Persistence round-trip | ``test_store.py`` | Mapping field values; asserts read-back == written values |
| 6 - Expiration boundary | ``test_url_service.py`` | Mappings with expires_at in the past; asserts 410 and no count increment |
| 7 - Stats completeness | ``test_url_service.py`` | Any short code, expired or not; asserts all fields present |
| 8 - Custom code conflict detection | ``test_url_service.py`` | Any stored code + any original URL; asserts 409 |
| 9 - Validation rejection | ``test_url_service.py`` | Invalid custom codes and invalid expires_in values; asserts 422 |
| 10 - Expiration timestamp recorded | ``test_url_service.py`` | Any valid expires_in (1 to 315576000); asserts expires_at accuracy |

"

$newContent = $before + $newTable + $after
Set-Content -Path $f -Value $newContent -NoNewline -Encoding UTF8
Write-Host "SUCCESS: $($newContent.Length) chars"
