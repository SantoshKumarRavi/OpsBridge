import 'dart:convert';
import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:opsbridge_flutter_analytics/main.dart';

const _secureStorageChannel = MethodChannel(
  'plugins.it_nomads.com/flutter_secure_storage',
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_secureStorageChannel, (call) async => null);
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_secureStorageChannel, null);
  });

  testWidgets('loads tenant cases and displays status summaries', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final client = MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.headers['x-tenant-id'], 'demo-tenant');
      expect(request.body, isNot(contains('email')));
      return http.Response(
        jsonEncode({
          'data': {
            'cases': {
              'total': 1,
              'items': [
                {
                  'id': 'case-1',
                  'workerName': 'Riya Sen',
                  'role': 'Care coordinator',
                  'country': 'India',
                  'status': 'review_required',
                  'version': 1,
                },
              ],
            },
          },
        }),
        200,
      );
    });

    await tester.pumpWidget(
      MaterialApp(home: CaseDashboard(graphqlClient: client)),
    );
    await tester.pumpAndSettle();

    expect(find.text('Frontline onboarding snapshot'), findsOneWidget);
    expect(find.text('Riya Sen'), findsOneWidget);
    expect(find.text('Care coordinator · India'), findsOneWidget);
    expect(find.text('review required'), findsOneWidget);
  });

  testWidgets('shows an actionable error when the GraphQL request fails', (
    tester,
  ) async {
    final client = MockClient((_) async => http.Response('unavailable', 503));

    await tester.pumpWidget(
      MaterialApp(home: CaseDashboard(graphqlClient: client)),
    );
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Could not load cases: Exception: API returned 503'),
      findsOneWidget,
    );
    expect(find.text('Retry'), findsOneWidget);
  });
}
