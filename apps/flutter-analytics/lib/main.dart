import 'dart:convert';

import 'package:material_ui/material_ui.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

const graphqlUrl = String.fromEnvironment(
  'OPSBRIDGE_GRAPHQL_URL',
  defaultValue: 'http://10.0.2.2:8010/graphql',
);
const oidcIssuer = String.fromEnvironment('OPSBRIDGE_OIDC_ISSUER');
const oidcClientId = 'opsbridge-flutter';
const oidcRedirect = 'opsbridgeflutter://oauth2redirect';

void main() => runApp(const OpsBridgeFlutterApp());

class OpsBridgeFlutterApp extends StatelessWidget {
  const OpsBridgeFlutterApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'OpsBridge Flutter',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorSchemeSeed: const Color(0xff1c4939),
          useMaterial3: true,
        ),
        home: const CaseDashboard(),
      );
}

class CaseDashboard extends StatefulWidget {
  const CaseDashboard({super.key, this.graphqlClient});

  final http.Client? graphqlClient;

  @override
  State<CaseDashboard> createState() => _CaseDashboardState();
}

class _CaseDashboardState extends State<CaseDashboard> {
  final _storage = const FlutterSecureStorage();
  final _appAuth = const FlutterAppAuth();
  late final http.Client _graphqlClient = widget.graphqlClient ?? http.Client();
  bool get _ownsGraphqlClient => widget.graphqlClient == null;
  List<Map<String, dynamic>> _cases = [];
  String? _accessToken;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadToken().then((_) => _loadCases());
  }

  @override
  void dispose() {
    if (_ownsGraphqlClient) _graphqlClient.close();
    super.dispose();
  }

  Future<void> _loadToken() async {
    _accessToken = await _storage.read(key: 'opsbridge.access-token');
    await _refreshIfNeeded();
  }

  Future<void> _storeTokenResponse(
    String? access,
    String? refresh,
    DateTime? expiresAt,
  ) async {
    if (access == null) {
      throw Exception('Identity provider returned no access token.');
    }
    _accessToken = access;
    await _storage.write(key: 'opsbridge.access-token', value: access);
    if (refresh != null) {
      await _storage.write(key: 'opsbridge.refresh-token', value: refresh);
    }
    if (expiresAt != null) {
      await _storage.write(
        key: 'opsbridge.access-expires-at',
        value: expiresAt.millisecondsSinceEpoch.toString(),
      );
    }
  }

  Future<void> _refreshIfNeeded() async {
    final expiry = int.tryParse(
      await _storage.read(key: 'opsbridge.access-expires-at') ?? '',
    );
    final needsRefresh = _accessToken == null ||
        expiry == null ||
        expiry <=
            DateTime.now()
                .add(const Duration(seconds: 60))
                .millisecondsSinceEpoch;
    if (!needsRefresh) return;
    final refreshToken = await _storage.read(key: 'opsbridge.refresh-token');
    if (refreshToken == null || oidcIssuer.isEmpty) {
      if (_accessToken == null) return;
      await _storage.delete(key: 'opsbridge.access-token');
      _accessToken = null;
      return;
    }
    try {
      final response = await _appAuth.token(
        TokenRequest(
          oidcClientId,
          oidcRedirect,
          issuer: oidcIssuer,
          refreshToken: refreshToken,
          scopes: const ['openid', 'profile', 'email', 'offline_access'],
        ),
      );
      await _storeTokenResponse(
        response.accessToken,
        response.refreshToken,
        response.accessTokenExpirationDateTime,
      );
    } catch (_) {
      await _storage.delete(key: 'opsbridge.access-token');
      await _storage.delete(key: 'opsbridge.refresh-token');
      await _storage.delete(key: 'opsbridge.access-expires-at');
      _accessToken = null;
    }
  }

  Future<void> _signIn() async {
    if (oidcIssuer.isEmpty) {
      setState(
        () => _error = 'Set OPSBRIDGE_OIDC_ISSUER to enable Keycloak sign-in.',
      );
      return;
    }
    try {
      final response = await _appAuth.authorizeAndExchangeCode(
        AuthorizationTokenRequest(
          oidcClientId,
          oidcRedirect,
          issuer: oidcIssuer,
          scopes: const ['openid', 'profile', 'email', 'offline_access'],
        ),
      );
      await _storeTokenResponse(
        response.accessToken,
        response.refreshToken,
        response.accessTokenExpirationDateTime,
      );
      await _loadCases();
    } catch (error) {
      setState(() => _error = 'Sign-in did not complete: $error');
    }
  }

  Future<void> _signOut() async {
    await _storage.delete(key: 'opsbridge.access-token');
    await _storage.delete(key: 'opsbridge.refresh-token');
    await _storage.delete(key: 'opsbridge.access-expires-at');
    setState(() => _accessToken = null);
    await _loadCases();
  }

  Future<void> _loadCases() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await _refreshIfNeeded();
      final headers = <String, String>{
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      };
      if (_accessToken != null) {
        headers['Authorization'] = 'Bearer $_accessToken';
      } else {
        headers['X-Tenant-Id'] = 'demo-tenant'; // Local mock identity only.
      }
      final response = await _graphqlClient.post(
        Uri.parse(graphqlUrl),
        headers: headers,
        body: jsonEncode({
          'query':
              'query DashboardCases { cases(first: 50) { total items { id workerName role country status version } } }',
        }),
      );
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception('API returned ${response.statusCode}');
      }
      final payload = jsonDecode(response.body) as Map<String, dynamic>;
      if (payload['errors'] != null) {
        throw Exception('GraphQL query returned an error');
      }
      final data = payload['data'] as Map<String, dynamic>;
      final rows =
          ((data['cases'] as Map<String, dynamic>)['items'] as List<dynamic>? ??
                  [])
              .cast<Map<String, dynamic>>()
              .map((item) => {...item, 'worker_name': item['workerName']})
              .toList();
      setState(() => _cases = rows);
    } catch (error) {
      setState(() => _error = 'Could not load cases: $error');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('OpsBridge · Flutter'),
          actions: [
            IconButton(
              onPressed: _loadCases,
              icon: const Icon(Icons.refresh),
              tooltip: 'Refresh',
            ),
            if (_accessToken == null)
              TextButton(onPressed: _signIn, child: const Text('Sign in'))
            else
              TextButton(onPressed: _signOut, child: const Text('Sign out')),
          ],
        ),
        body: LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 800;
            final counts = <String, int>{};
            for (final item in _cases) {
              final status = (item['status'] ?? 'unknown').toString();
              counts[status] = (counts[status] ?? 0) + 1;
            }
            final metrics = [
              _Metric(
                label: 'Total cases',
                value: _cases.length.toString(),
                icon: Icons.groups_2_outlined,
              ),
              _Metric(
                label: 'Needs review',
                value: (counts['review_required'] ?? 0).toString(),
                icon: Icons.fact_check_outlined,
              ),
              _Metric(
                label: 'Processing',
                value: (counts['processing'] ?? 0).toString(),
                icon: Icons.hourglass_top,
              ),
              _Metric(
                label: 'Approved',
                value: (counts['approved'] ?? 0).toString(),
                icon: Icons.verified_outlined,
              ),
            ];
            return RefreshIndicator(
              onRefresh: _loadCases,
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  Text(
                    'Frontline onboarding snapshot',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'A standalone Flutter client over the shared tenant-aware API.',
                  ),
                  const SizedBox(height: 20),
                  GridView.count(
                    crossAxisCount: wide ? 4 : 2,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    mainAxisExtent: wide ? 128 : 140,
                    children: metrics
                        .map((metric) => Card(
                              child: Padding(
                                padding: const EdgeInsets.all(16),
                                child: Row(
                                  children: [
                                    Icon(metric.icon),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Text(
                                            metric.label,
                                            maxLines: 2,
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                          Text(
                                            metric.value,
                                            style: Theme.of(context)
                                                .textTheme
                                                .headlineMedium,
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ))
                        .toList(),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    MaterialBanner(
                      content: Text(_error!),
                      actions: [
                        TextButton(
                          onPressed: _loadCases,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ],
                  const SizedBox(height: 16),
                  if (_loading) const LinearProgressIndicator(),
                  Text(
                    'Recent onboarding cases',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  ..._cases.take(50).map(
                        (item) => Card(
                          child: ListTile(
                            leading: const CircleAvatar(
                              child: Icon(Icons.person_outline),
                            ),
                            title: Text(
                              (item['worker_name'] ?? 'Unknown worker')
                                  .toString(),
                            ),
                            subtitle: Text(
                              '${item['role'] ?? 'Role pending'} · ${item['country'] ?? ''}',
                            ),
                            trailing: Chip(
                              label: Text(
                                (item['status'] ?? 'unknown')
                                    .toString()
                                    .replaceAll(
                                      '_',
                                      ' ',
                                    ),
                              ),
                            ),
                          ),
                        ),
                      ),
                ],
              ),
            );
          },
        ),
      );
}

class _Metric {
  const _Metric({required this.label, required this.value, required this.icon});
  final String label;
  final String value;
  final IconData icon;
}
