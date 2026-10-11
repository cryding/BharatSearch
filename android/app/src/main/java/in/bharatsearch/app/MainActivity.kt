package in.bharatsearch.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.net.URLEncoder

private val http = OkHttpClient()

data class SearchResult(val title: String, val url: String, val description: String)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { BharatSearchApp() }
    }
}

@Composable
private fun BharatSearchApp() {
    var query by remember { mutableStateOf("") }
    var apiUrl by remember { mutableStateOf(BuildConfig.API_BASE_URL) }
    var editingApi by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("Search pages indexed by BharatSearch") }
    var results by remember { mutableStateOf(emptyList<SearchResult>()) }
    val scope = rememberCoroutineScope()

    MaterialTheme(colorScheme = lightColorScheme(primary = androidx.compose.ui.graphics.Color(0xFF16834A))) {
        Scaffold { padding ->
            Column(Modifier.fillMaxSize().padding(padding).padding(20.dp)) {
                Text("🇮🇳 BharatSearch", style = MaterialTheme.typography.headlineMedium)
                Text("Explore the web. Discover more.", style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(22.dp))
                OutlinedTextField(
                    value = query, onValueChange = { query = it }, modifier = Modifier.fillMaxWidth(),
                    label = { Text("Search the indexed web") }, singleLine = true
                )
                Spacer(Modifier.height(8.dp))
                Button(onClick = {
                    val term = query.trim()
                    if (term.isEmpty()) { message = "Enter a search query."; return@Button }
                    loading = true
                    message = "Searching…"
                    scope.launch {
                        try {
                            val encoded = URLEncoder.encode(term, "UTF-8")
                            val request = Request.Builder().url("${apiUrl.trimEnd('/')}/api/search?q=$encoded").build()
                            val data = withContext(Dispatchers.IO) {
                                http.newCall(request).execute().use { response ->
                                    if (!response.isSuccessful) error("API HTTP ${response.code}")
                                    JSONObject(response.body?.string() ?: "{}")
                                }
                            }
                            val array = data.optJSONArray("results")
                            results = (0 until (array?.length() ?: 0)).map { i ->
                                val item = array!!.getJSONObject(i)
                                SearchResult(item.optString("title", item.optString("url")),
                                    item.optString("url"), item.optString("description", ""))
                            }
                            message = "${results.size} indexed results"
                        } catch (e: Exception) {
                            message = "Search API unavailable. Check API URL and backend."
                        } finally { loading = false }
                    }
                }, modifier = Modifier.fillMaxWidth(), enabled = !loading) {
                    Text(if (loading) "Searching…" else "Search Bharat")
                }
                TextButton(onClick = { editingApi = !editingApi }) { Text("⚙ Search API settings") }
                if (editingApi) {
                    OutlinedTextField(apiUrl, { apiUrl = it }, modifier = Modifier.fillMaxWidth(),
                        label = { Text("API base URL") }, singleLine = true)
                    Text("Use your deployed HTTPS API in production. Emulator local API: http://10.0.2.2:8000")
                }
                Spacer(Modifier.height(8.dp))
                Text(message, style = MaterialTheme.typography.bodySmall)
                LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    items(results) { result ->
                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(14.dp)) {
                                Text(result.title, style = MaterialTheme.typography.titleMedium)
                                Text(result.url, style = MaterialTheme.typography.labelSmall)
                                if (result.description.isNotBlank()) Text(result.description)
                            }
                        }
                    }
                }
            }
        }
    }
}
