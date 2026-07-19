#pragma once

#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <iomanip>

class Fraction
{
public:
    constexpr Fraction()
        : numerator_(0),
          denominator_(1)
    {
    }

    constexpr Fraction(std::int64_t numerator, std::int64_t denominator = 1)
        : numerator_(numerator),
          denominator_(denominator)
    {
        normalize();
    }

    [[nodiscard]]
    constexpr std::int64_t numerator() const
    {
        return numerator_;
    }

    [[nodiscard]]
    constexpr std::int64_t denominator() const
    {
        return denominator_;
    }

    constexpr Fraction operator+(const Fraction& other) const
    {
        return Fraction(
            numerator_ * other.denominator_ +
            other.numerator_ * denominator_,
            denominator_ * other.denominator_);
    }

    constexpr Fraction operator-(const Fraction& other) const
    {
        return Fraction(
            numerator_ * other.denominator_ -
            other.numerator_ * denominator_,
            denominator_ * other.denominator_);
    }

    constexpr Fraction operator*(const Fraction& other) const
    {
        return Fraction(
            numerator_ * other.numerator_,
            denominator_ * other.denominator_);
    }

    constexpr Fraction operator/(const Fraction& other) const
    {
        assert (other.numerator_ != 0);

        return Fraction(
            numerator_ * other.denominator_,
            denominator_ * other.numerator_);
    }

    constexpr Fraction& operator+=(const Fraction& other)
    {
        *this = *this + other;
        return *this;
    }

    constexpr Fraction& operator-=(const Fraction& other)
    {
        *this = *this - other;
        return *this;
    }

    constexpr Fraction& operator*=(const Fraction& other)
    {
        *this = *this * other;
        return *this;
    }

    constexpr Fraction& operator/=(const Fraction& other)
    {
        *this = *this / other;
        return *this;
    }

    constexpr bool operator==(const Fraction& other) const
    {
        return numerator_ == other.numerator_
            && denominator_ == other.denominator_;
    }

    constexpr bool operator!=(const Fraction& other) const
    {
        return !(*this == other);
    }

    constexpr bool operator<(const Fraction& other) const
    {
        return numerator_ * other.denominator_
             < other.numerator_ * denominator_;
    }

    constexpr bool operator<=(const Fraction& other) const
    {
        return !(*this > other);
    }

    constexpr bool operator>(const Fraction& other) const
    {
        return other < *this;
    }

    constexpr bool operator>=(const Fraction& other) const
    {
        return !(*this < other);
    }

    [[nodiscard]]
    std::string to_string() const
    {
        if (denominator_ == 1)
        {
            return std::to_string(numerator_);
        }

        return std::to_string(numerator_) + "/" + std::to_string(denominator_);
    }

    [[nodiscard]]
    std::string to_decimal_string() const
    {
        std::ostringstream oss;
        oss << std::setprecision(16)
            << to_double();
        return oss.str();
    }

    [[nodiscard]]
    constexpr double to_double() const
    {
        return static_cast<double>(numerator_) /
               static_cast<double>(denominator_);
    }

private:
    constexpr void normalize()
    {
        assert (denominator_ != 0);

        if (denominator_ < 0)
        {
            numerator_ = -numerator_;
            denominator_ = -denominator_;
        }

        const auto gcd = std::gcd(numerator_, denominator_);

        numerator_ /= gcd;
        denominator_ /= gcd;
    }

    std::int64_t numerator_;
    std::int64_t denominator_;
};
