cout << "Enter your value: " << endl;
int n;
cin >> n;

int sum = 0;
for (int i = 0; i <= n; i = i + 1) {
    sum = sum + i;
}
// This is a test!
cout << "sum = " << sum << endl;

switch (n) {
    case 0:
        cout << "n was zero" << endl;
        break;
    case 1:
        cout << "n was one" << endl;
        break;
    default:
        cout << "n was something else" << endl;
}

int x = 5;
if (x % 2 == 1) {
    cout << "x is odd" << endl;
} else {
    cout << "x is even" << endl;
}

int c = 3;
while (c > 0) {
    cout << "c = " << c << endl;
    c = c - 1;
}
