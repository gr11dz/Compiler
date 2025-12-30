// Compute sum of 0..n with a for loop and show switch behavior
print("Enter your value: ");
int n = int(input());
int sum = 0;

for (int i = 0; i <= n; i = i + 1) {
  sum = sum + i;
}

print("sum = " + string(sum));

switch (n) {
  case 0: {
    print("n was zero");
    break;
  }
  case 1: {
    print("n was one");
    break;
  }
  default: {
    print("n was something else");
  }
}

int x = 5;
if (x % 2 == 1) {
  print("x is odd");
} else {
  print("x is even");
}

// while loop demo
int c = 3;
while (c > 0) {
  print("c = " + string(c));
  c = c - 1;
}
