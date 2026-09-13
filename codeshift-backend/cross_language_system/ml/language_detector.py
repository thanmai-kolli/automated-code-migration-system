import os
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "language_model.pkl")

class MLLanguageDetector:

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4)
        )
        self.model = RandomForestClassifier(n_estimators=100)

        if os.path.exists(MODEL_PATH):
            self._load_model()
        else:
            self._train_model()

    # -------------------------------------
    # Training Data
    # -------------------------------------
    def _train_model(self):

        print("🔥 Training language detection model...")

        training_data = [
            # C
            ("#include <stdio.h>\nint main(){ printf(\"Hello\"); }", "c"),
            ("scanf(\"%d\", &x);", "c"),
            ("malloc(sizeof(int));", "c"),

            # C++
            ("#include <iostream>\nusing namespace std;", "cpp"),
            ("cout << \"Hello\";", "cpp"),
            ("cin >> x;", "cpp"),
            ("std::vector<int> v;", "cpp"),

            # Java
            ("public class Test { public static void main(String[] args){} }", "java"),
            ("System.out.println(\"Hello\");", "java"),

            # Python
            ("def main(): print(\"Hello\")", "python"),
            ("import os", "python"),
            ("for i in range(10):", "python")
        ]

        texts, labels = zip(*training_data)

        X = self.vectorizer.fit_transform(texts)
        self.model.fit(X, labels)

        joblib.dump((self.vectorizer, self.model), MODEL_PATH)
        print("✅ Model saved at:", MODEL_PATH)
        

    def _load_model(self):
        self.vectorizer, self.model = joblib.load(MODEL_PATH)

    def predict(self, code):
        X = self.vectorizer.transform([code])
        return self.model.predict(X)[0]
    

if __name__ == "__main__":
    detector = MLLanguageDetector()
    print(detector.predict('#include <iostream>\ncout << "Hello";'))